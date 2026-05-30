from __future__ import annotations

import tempfile
import unittest
from unittest import mock
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.organize.session import SessionBook
from app.services.organize.identify import apply_source_candidate_tmdb_override, run_identify_phase, scan_session
from app.services.organize.review import (
    apply_conflict_review_action,
    validate_accepted_conflict_scope,
)
from app.services.organize.review import (
    set_plan_item_decision,
    set_source_candidate_decision,
)
from app.services.organize.source import SourceEdit, source_candidate_detail, source_file_detail
from app.services.organize.session import OrganizeSessionConflict
from app.services.identify.preview import Preview
from app.core.error import ConfigurationError
from app.infra.db.store import Store
from app.domain.organize import CandidateDecision, OrganizeSessionState
from app.domain.result import ResultStatus
from app.domain.match import ConfidenceLevel
from app.domain.media import MediaCandidate, MediaType
from app.domain.origin import OriginTrigger
from app.domain.organize import CandidatePreview, OrganizePlanItem, source_file_id
from app.services.identify.candidate import CandidateMatch
from app.domain.origin import OrganizePolicy, Origin
from app.domain.depot import ResolveMode, Depot, TransferPolicy
from app.domain.match import MatchResult, TMDBCandidate
from app.services.depot.lock import DepotLockRegistry
from app.services.activity.recorder import ActivityRecorder
from app.services.organize.execute import OrganizeExecutor
from app.services.organize.candidate import source_review_candidates as build_source_review_candidates
from app.domain.tv import TVEpisodeCatalog
from app.engines.resolve.identity import package_identity
from app.engines.plan.tv.evidence import TV_EPISODE_PLAN_EVIDENCE_KEY
from app.engines.plan.tv.planner import TVEpisodePlanner
from app.engines.scan.source import scan_movie_root, scan_tv_root
from support import FakeTVEpisodeCatalogProvider, FakeTVEpisodeExtractor, TEST_MEDIA_EXTENSIONS


class OrganizeSessionWorkflowTests(unittest.TestCase):
    def test_source_review_candidates_sort_by_pinyin_display_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            candidates = [
                MediaCandidate(id="test-10", media_type=MediaType.MOVIE, source_root=root, candidate_path=root / "测试10", display_name="测试10"),
                MediaCandidate(id="avatar", media_type=MediaType.MOVIE, source_root=root, candidate_path=root / "阿凡达", display_name="阿凡达"),
                MediaCandidate(id="test-2", media_type=MediaType.MOVIE, source_root=root, candidate_path=root / "测试2", display_name="测试2"),
                MediaCandidate(id="tagged", media_type=MediaType.MOVIE, source_root=root, candidate_path=root / "[特别]", display_name="[特别]"),
            ]

            manager.mark_scanned(task.id, candidates)

            review = build_source_review_candidates(manager.get(task.id), extensions=TEST_MEDIA_EXTENSIONS)
            self.assertEqual([candidate.display_name for candidate in review], ["[特别]", "阿凡达", "测试2", "测试10"])

    def test_manual_origin_slot_conflict_and_cancel_release(self) -> None:
        manager = SessionBook()
        origin = self._origin(Path("C:/media/manual"))

        task = manager.create_for_origin(origin)
        with self.assertRaises(OrganizeSessionConflict):
            manager.create_for_origin(origin)

        manager.cancel(task.id)
        self.assertEqual(manager.create_for_origin(origin).path, origin.path)

    def test_stale_task_cleanup_releases_slot_after_idle_timeout(self) -> None:
        current = datetime(2026, 5, 2, tzinfo=timezone.utc)
        manager = SessionBook(idle_timeout_seconds=10, now=lambda: current)
        origin = self._origin(Path("C:/media/manual"))

        task = manager.create_for_origin(origin)
        manager.mark_scanned(task.id, [])
        current = current + timedelta(seconds=11)

        self.assertEqual(manager.active_sessions(), [])
        self.assertEqual(manager.create_for_origin(origin).path, origin.path)
        self.assertNotIn(task.id, [item.id for item in manager.active_sessions()])

    def test_active_work_states_do_not_expire_after_idle_timeout(self) -> None:
        for state in (
            OrganizeSessionState.SCANNING,
            OrganizeSessionState.IDENTIFYING,
            OrganizeSessionState.ORGANIZING,
        ):
            with self.subTest(state=state.value):
                current = datetime(2026, 5, 2, tzinfo=timezone.utc)
                manager = SessionBook(idle_timeout_seconds=10, now=lambda: current)
                origin = self._origin(Path(f"C:/media/{state.value}"))
                task = manager.create_for_origin(origin)
                if state == OrganizeSessionState.IDENTIFYING:
                    manager.mark_scanned(task.id, [])
                    manager.start_identify(task.id)
                elif state == OrganizeSessionState.ORGANIZING:
                    manager.mark_scanned(task.id, [])
                    manager.start_identify(task.id)
                    manager.mark_identified(task.id, candidate_matches={}, plan_items=[])
                    manager.start_organize(task.id)

                current = current + timedelta(seconds=11)

                sessions = manager.active_sessions()
                self.assertEqual([item.id for item in sessions], [task.id])
                self.assertEqual(sessions[0].state, state)
                with self.assertRaises(OrganizeSessionConflict):
                    manager.create_for_origin(origin)

    def test_scan_failure_cancels_session_and_releases_slot(self) -> None:
        manager = SessionBook()
        origin = self._origin(Path("C:/media/manual"))
        task = manager.create_for_origin(origin)

        with mock.patch("app.services.organize.identify.scan_source_root", side_effect=RuntimeError("scan failed")):
            with self.assertRaises(RuntimeError):
                scan_session(manager, task.id, extensions=TEST_MEDIA_EXTENSIONS)

        self.assertEqual(manager.active_sessions(), [])
        self.assertEqual(manager.create_for_origin(origin).path, origin.path)

    def test_identify_failure_returns_session_to_scanned(self) -> None:
        class BrokenMatcher:
            def match_batch(self, _media_candidates):
                raise RuntimeError("identify failed")

        manager = SessionBook()
        task = manager.create_for_origin(self._origin(Path("C:/media/manual")))
        manager.mark_scanned(task.id, [])

        with self.assertRaises(RuntimeError):
            run_identify_phase(manager, task.id, matcher=BrokenMatcher(), extensions=TEST_MEDIA_EXTENSIONS)

        self.assertEqual(manager.get(task.id).state, OrganizeSessionState.SCANNED)

    def test_identify_uses_selected_scanned_candidates_and_prunes_ignored_after_success(self) -> None:
        class RecordingMatcher:
            def __init__(self):
                self.requested_ids: list[str] = []

            def match_batch(self, media_candidates):
                self.requested_ids = [candidate.id for candidate in media_candidates]
                return {
                    candidate.id: MatchResult(
                        candidate_id=candidate.id,
                        media_type=MediaType.MOVIE,
                        confidence=ConfidenceLevel.HIGH,
                        title="Movie",
                        year=2020,
                        tmdb_id=1,
                        metadata={"title": "Movie", "release_year": 2020, "tmdb_id": 1},
                    )
                    for candidate in media_candidates
                }

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Accepted.2020.mkv").write_text("accepted", encoding="utf-8")
            (root / "Ignored.2020.mkv").write_text("ignored", encoding="utf-8")
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            media_candidates = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)
            ignored = next(candidate for candidate in media_candidates if candidate.display_name.startswith("Ignored"))
            accepted = next(candidate for candidate in media_candidates if candidate.display_name.startswith("Accepted"))
            manager.mark_scanned(task.id, media_candidates)
            set_source_candidate_decision(manager.get(task.id), ignored.id, CandidateDecision.IGNORE)
            matcher = RecordingMatcher()

            identified = run_identify_phase(
                manager,
                task.id,
                matcher=matcher,
                extensions=TEST_MEDIA_EXTENSIONS,
            )

            self.assertEqual(matcher.requested_ids, [accepted.id])
            self.assertEqual([candidate.id for candidate in identified.media_candidates], [accepted.id])
            self.assertNotIn(ignored.id, identified.source_states)
            self.assertEqual({item.source_candidate_id for item in identified.plan_items}, {accepted.id})

    def test_identify_failure_preserves_scanned_selection_choices(self) -> None:
        class BrokenMatcher:
            def match_batch(self, _media_candidates):
                raise RuntimeError("identify failed")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Movie.2020.mkv").write_text("movie", encoding="utf-8")
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager.mark_scanned(task.id, [media_candidate])
            set_source_candidate_decision(manager.get(task.id), media_candidate.id, CandidateDecision.IGNORE)

            with self.assertRaises(RuntimeError):
                run_identify_phase(manager, task.id, matcher=BrokenMatcher(), extensions=TEST_MEDIA_EXTENSIONS)

            scanned = manager.get(task.id)
            self.assertEqual(scanned.state, OrganizeSessionState.SCANNED)
            self.assertEqual(scanned.source_states[media_candidate.id].selection_decision, CandidateDecision.IGNORE)
            self.assertEqual([candidate.id for candidate in scanned.media_candidates], [media_candidate.id])

    def test_organize_failure_returns_session_to_identified(self) -> None:
        manager = SessionBook()
        task = manager.create_for_origin(self._origin(Path("C:/media/manual")))
        manager.mark_scanned(task.id, [])
        manager.start_identify(task.id)
        manager.mark_identified(task.id, candidate_matches={}, plan_items=[])
        manager.start_organize(task.id)

        manager.fail_organize(task.id)

        self.assertEqual(manager.get(task.id).state, OrganizeSessionState.IDENTIFIED)

    def test_decision_rules(self) -> None:
        manager = SessionBook()
        task = manager.create_for_origin(self._origin(Path("C:/media/manual")))
        high = self._candidate("high", ConfidenceLevel.HIGH)
        high.preview = CandidatePreview(proposed_relative_path=Path("High/High.mkv"))
        medium = self._candidate("medium", ConfidenceLevel.MEDIUM, metadata={"title": "Movie"}, source="auto")
        medium.preview = CandidatePreview(proposed_relative_path=Path("Medium/Medium.mkv"))
        blocked = self._candidate("blocked", ConfidenceLevel.LOW)
        blocked.metadata = None
        blocked.metadata_source = None
        manager.mark_scanned(task.id, [])
        manager.start_identify(task.id)
        manager.mark_identified(
            task.id,
            candidate_matches={},
            plan_items=[high, medium, blocked],
        )

        items_by_id = {item.id: item for item in manager.get(task.id).plan_items}
        self.assertEqual(items_by_id["high"].user_decision, CandidateDecision.ACCEPT)
        self.assertIsNone(items_by_id["medium"].user_decision)
        self.assertIsNone(items_by_id["blocked"].user_decision)

        self.assertEqual(
            set_plan_item_decision(manager.get(task.id), "high", CandidateDecision.ACCEPT).user_decision,
            CandidateDecision.ACCEPT,
        )
        self.assertEqual(
            set_plan_item_decision(manager.get(task.id), "medium", CandidateDecision.ACCEPT).user_decision,
            CandidateDecision.ACCEPT,
        )
        with self.assertRaises(Exception):
            set_plan_item_decision(manager.get(task.id), "blocked", CandidateDecision.ACCEPT)

    def test_ad_hoc_source_overlap_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            managed = root / "managed"
            source = managed / "sub"
            source.mkdir(parents=True)
            manager = SessionBook()

            with self.assertRaises(ConfigurationError):
                manager.create_ad_hoc(
                    source_path=source,
                    media_type=MediaType.MOVIE,
                    policy=OrganizePolicy(target_depot_id="Depot"),
                    origins=[self._origin(managed)],
                )

    def test_organize_skips_missing_source_and_records_activity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            try:
                Depot = self._depot(root / "Depot")
                candidate = self._candidate("missing", ConfidenceLevel.HIGH, source_path=root / "missing.mkv")
                candidate.user_decision = CandidateDecision.ACCEPT
                result = self._organizer(store).organize_candidate(candidate, Depot)

                self.assertEqual(result.status, ResultStatus.SKIPPED)
                self.assertEqual(len(store.list_activity_events()), 1)
            finally:
                store.close()

    def test_movie_organize_skips_existing_destination_and_preserves_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            try:
                source = root / "source.mkv"
                source.write_text("new", encoding="utf-8")
                destination = root / "Depot" / "Movie" / "Movie.mkv"
                destination.parent.mkdir(parents=True)
                destination.write_text("old-content", encoding="utf-8")
                Depot = self._depot(root / "Depot")
                candidate = self._candidate("movie", ConfidenceLevel.HIGH, source_path=source)
                candidate.user_decision = CandidateDecision.ACCEPT

                result = self._organizer(store).organize_candidate(
                    candidate,
                    Depot,
                    context={"origin_id": "manual", "origin_path": str(root), "organize_rule_id": "movie-rule"},
                    source_root=root,
                )

                self.assertEqual(result.status, ResultStatus.SKIPPED)
                self.assertEqual(source.read_text(encoding="utf-8"), "new")
                self.assertEqual(destination.read_text(encoding="utf-8"), "old-content")
                entry = store.list_activity_events()[0]
                self.assertEqual(entry.context["origin_id"], "manual")
                self.assertEqual(entry.context["organize_rule_id"], "movie-rule")
                self.assertEqual(entry.context["skip_reason"], "movie_origin_depot_resolve_disabled")
                self.assertTrue(entry.context["movie_origin_depot_resolve_disabled"])
                self.assertEqual(entry.context["source_relative_path"], "source.mkv")
                self.assertEqual(entry.context["depot_relative_path"], "Movie/Movie.mkv")
                self.assertEqual(entry.context["destination_relative_path"], "Movie/Movie.mkv")
            finally:
                store.close()

    def test_tv_organize_replaces_destination_and_records_activity_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            try:
                source = root / "source.mkv"
                source.write_text("new", encoding="utf-8")
                destination = root / "Depot" / "Movie" / "Movie.mkv"
                destination.parent.mkdir(parents=True)
                destination.write_text("old-content", encoding="utf-8")
                Depot = self._tv_depot(root / "Depot")
                candidate = self._candidate("tv", ConfidenceLevel.HIGH, source_path=source)
                candidate.user_decision = CandidateDecision.ACCEPT

                result = self._organizer(store).organize_candidate(
                    candidate,
                    Depot,
                    context={"origin_id": "manual", "origin_path": str(root), "organize_rule_id": "tv-rule"},
                    source_root=root,
                )

                self.assertEqual(result.status, ResultStatus.SUCCEEDED)
                self.assertFalse(source.exists())
                self.assertEqual(destination.read_text(encoding="utf-8"), "new")
                entry = store.list_activity_events()[0]
                self.assertEqual(entry.context["overwritten_size"], len("old-content"))
                self.assertEqual(entry.context["origin_id"], "manual")
                self.assertEqual(entry.context["organize_rule_id"], "tv-rule")
                self.assertEqual(entry.context["source_relative_path"], "source.mkv")
                self.assertEqual(entry.context["depot_relative_path"], "Movie/Movie.mkv")
                self.assertEqual(entry.context["destination_relative_path"], "Movie/Movie.mkv")
                self.assertEqual(entry.context["metadata_tmdb_id"], 1)
                self.assertEqual(entry.context["metadata_title"], "Movie")
                self.assertEqual(entry.context["metadata_year"], 2020)
            finally:
                store.close()

    def test_full_organize_candidates_blocks_existing_movie_package_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            try:
                source = root / "Avatar.2009.mkv"
                source.write_text("new", encoding="utf-8")
                package_root = root / "Depot" / "Avatar (2009) {tmdb-19995}"
                package_root.mkdir(parents=True)
                (package_root / "poster.jpg").write_text("old-poster", encoding="utf-8")
                Depot = self._depot(root / "Depot")
                candidate = self._candidate("movie", ConfidenceLevel.HIGH, source_path=source)
                candidate.preview = CandidatePreview(proposed_relative_path=Path("Avatar (2009) {tmdb-19995}/Avatar.2009.mkv"))
                candidate.user_decision = CandidateDecision.ACCEPT

                result = self._organizer(store).organize_candidates([candidate], Depot, source_root=root)

                self.assertEqual(result.skipped, 1)
                self.assertTrue(source.exists())
                self.assertFalse((package_root / "Avatar.2009.mkv").exists())
                context = store.list_activity_events()[0].context
                self.assertEqual(context["package_conflict_reason"], "package_exists")
                self.assertEqual(context["package_root_relative_path"], "Avatar (2009) {tmdb-19995}")
            finally:
                store.close()

    def test_full_organize_candidates_replace_decision_replaces_movie_package_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            try:
                source = root / "Avatar.2009.mkv"
                source.write_text("new", encoding="utf-8")
                package_root = root / "Depot" / "Avatar (2009) {tmdb-19995}"
                package_root.mkdir(parents=True)
                leftover = package_root / "poster.jpg"
                leftover.write_text("old-poster", encoding="utf-8")
                Depot = self._depot(root / "Depot")
                candidate = self._candidate("movie", ConfidenceLevel.HIGH, source_path=source)
                candidate.preview = CandidatePreview(proposed_relative_path=Path("Avatar (2009) {tmdb-19995}/Avatar.2009.mkv"))
                candidate.user_decision = CandidateDecision.ACCEPT

                result = self._organizer(store).organize_candidates(
                    [candidate],
                    Depot,
                    source_root=root,
                    resolve_decisions={"movie:Avatar (2009) {tmdb-19995}": "replace"},
                )

                self.assertEqual(result.moved, 1)
                self.assertFalse(source.exists())
                self.assertEqual((package_root / "Avatar.2009.mkv").read_text(encoding="utf-8"), "new")
                self.assertFalse(leftover.exists())
                self.assertTrue(store.list_activity_events()[0].context["package_replaced"])
            finally:
                store.close()

    def test_incremental_tv_organize_candidates_upserts_episode_video_and_subtitles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            try:
                source = root / "Example.Show.S01E01.mkv"
                source.write_text("new", encoding="utf-8")
                season_root = root / "Depot" / "Example Show (2020) {tmdb-1}" / "Season 1"
                season_root.mkdir(parents=True)
                old_video = season_root / "Example Show - S01E01 - Old.mp4"
                old_subtitle = season_root / "Example Show - S01E01 - Old.zh.srt"
                next_episode = season_root / "Example Show - S01E02 - Next.mp4"
                old_video.write_text("old-video", encoding="utf-8")
                old_subtitle.write_text("old-subtitle", encoding="utf-8")
                next_episode.write_text("next", encoding="utf-8")
                Depot = replace(self._tv_depot(root / "Depot"), resolve_mode=ResolveMode.INCREMENTAL)
                candidate = self._candidate("tv", ConfidenceLevel.HIGH, source_path=source)
                candidate.preview = CandidatePreview(
                    proposed_relative_path=Path("Example Show (2020) {tmdb-1}/Season 1/Example Show - S01E01 - Pilot.mkv")
                )
                candidate.evidence = {TV_EPISODE_PLAN_EVIDENCE_KEY: {"season": 1, "episode": 1, "end_episode": None}}
                candidate.user_decision = CandidateDecision.ACCEPT

                result = self._organizer(store).organize_candidates([candidate], Depot, source_root=root)

                self.assertEqual(result.moved, 1)
                self.assertFalse(old_video.exists())
                self.assertFalse(old_subtitle.exists())
                self.assertTrue(next_episode.exists())
                self.assertEqual((season_root / "Example Show - S01E01 - Pilot.mkv").read_text(encoding="utf-8"), "new")
                context = store.list_activity_events()[0].context
                self.assertEqual(context["resolve_mode"], "incremental")
                self.assertEqual(context["tv_planned_episode"], 1)
                self.assertEqual(len(context["incremental_deleted_existing"]), 2)
            finally:
                store.close()

    def test_organize_cleans_sidecar_only_source_folder_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            try:
                folder = root / "Avatar.2009"
                folder.mkdir()
                source = folder / "Avatar.2009.mkv"
                source.write_text("video", encoding="utf-8")
                (folder / "movie.nfo").write_text("metadata", encoding="utf-8")
                Depot = self._depot(root / "Depot")
                candidate = self._candidate("movie", ConfidenceLevel.HIGH, source_path=source)
                candidate.user_decision = CandidateDecision.ACCEPT

                result = self._organizer(store).organize_candidate(candidate, Depot, source_root=root)

                self.assertEqual(result.status, ResultStatus.SUCCEEDED)
                self.assertFalse(folder.exists())
                context = store.list_activity_events()[0].context
                self.assertTrue(context["cleanup_attempted"])
                self.assertIn("Avatar.2009", context["cleanup_removed_dirs"])
                self.assertIn("Avatar.2009/movie.nfo", context["cleanup_removed_files"])
            finally:
                store.close()

    def test_organize_preserves_source_folder_with_non_sidecar_leftover(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            try:
                folder = root / "Avatar.2009"
                folder.mkdir()
                source = folder / "Avatar.2009.mkv"
                source.write_text("video", encoding="utf-8")
                leftover = folder / "notes.json"
                leftover.write_text("keep", encoding="utf-8")
                Depot = self._depot(root / "Depot")
                candidate = self._candidate("movie", ConfidenceLevel.HIGH, source_path=source)
                candidate.user_decision = CandidateDecision.ACCEPT

                result = self._organizer(store).organize_candidate(candidate, Depot, source_root=root)

                self.assertEqual(result.status, ResultStatus.SUCCEEDED)
                self.assertTrue(folder.exists())
                self.assertTrue(leftover.exists())
                context = store.list_activity_events()[0].context
                self.assertEqual(context["cleanup_stopped_at"], "Avatar.2009")
                self.assertEqual(context["cleanup_stop_reason"], "contains_non_sidecar")
            finally:
                store.close()

    def test_organize_cleanup_removes_small_non_subtitle_leftover_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            try:
                folder = root / "Avatar.2009"
                folder.mkdir()
                source = folder / "Avatar.2009.mkv"
                source.write_bytes(b"x" * 20)
                sample = folder / "sample.mkv"
                sample.write_bytes(b"x")
                Depot = self._depot(root / "Depot")
                candidate = self._candidate("movie", ConfidenceLevel.HIGH, source_path=source)
                candidate.user_decision = CandidateDecision.ACCEPT

                result = self._organizer(store, min_non_subtitle_file_size_bytes=10).organize_candidate(
                    candidate,
                    Depot,
                    source_root=root,
                )

                self.assertEqual(result.status, ResultStatus.SUCCEEDED)
                self.assertFalse(folder.exists())
                context = store.list_activity_events()[0].context
                self.assertIn("Avatar.2009/sample.mkv", context["cleanup_removed_files"])
            finally:
                store.close()

    def test_organize_cleanup_preserves_small_subtitle_leftover_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            try:
                folder = root / "Avatar.2009"
                folder.mkdir()
                source = folder / "Avatar.2009.mkv"
                source.write_bytes(b"x" * 20)
                subtitle = folder / "Avatar.2009.srt"
                subtitle.write_bytes(b"x")
                Depot = self._depot(root / "Depot")
                candidate = self._candidate("movie", ConfidenceLevel.HIGH, source_path=source)
                candidate.user_decision = CandidateDecision.ACCEPT

                result = self._organizer(store, min_non_subtitle_file_size_bytes=10).organize_candidate(
                    candidate,
                    Depot,
                    source_root=root,
                )

                self.assertEqual(result.status, ResultStatus.SUCCEEDED)
                self.assertTrue(folder.exists())
                self.assertTrue(subtitle.exists())
                context = store.list_activity_events()[0].context
                self.assertEqual(context["cleanup_stopped_at"], "Avatar.2009")
                self.assertEqual(context["cleanup_stop_reason"], "contains_non_sidecar")
            finally:
                store.close()

    def test_organize_skips_source_that_becomes_below_min_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            try:
                source = root / "Avatar.2009.mkv"
                source.write_bytes(b"x")
                Depot = self._depot(root / "Depot")
                candidate = self._candidate("movie", ConfidenceLevel.HIGH, source_path=source)
                candidate.user_decision = CandidateDecision.ACCEPT

                result = self._organizer(store, min_non_subtitle_file_size_bytes=10).organize_candidate(
                    candidate,
                    Depot,
                    source_root=root,
                )

                self.assertEqual(result.status, ResultStatus.SKIPPED)
                self.assertTrue(source.exists())
                event = store.list_activity_events()[0]
                self.assertEqual(event.reason, "below_min_non_subtitle_file_size")
                self.assertEqual(event.context["skip_reason"], "below_min_non_subtitle_file_size")
                self.assertEqual(event.context["min_non_subtitle_file_size_bytes"], 10)
            finally:
                store.close()

    def test_scan_stores_source_candidate_without_plan_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie = root / "Avatar.2009.mkv"
            movie.write_text("x", encoding="utf-8")
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))

            scanned = manager.mark_scanned(task.id, [media_candidate])

            self.assertEqual(scanned.media_candidates[0].id, media_candidate.id)
            self.assertEqual(scanned.media_candidates[0].candidate_path, movie)
            self.assertEqual(scanned.plan_items, [])
            self.assertIn(source_file_id(media_candidate.id, Path("Avatar.2009.mkv")), scanned.file_states)

    def test_restart_scan_clears_identity_results_and_review_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie = root / "Avatar.2009.mkv"
            movie.write_text("x", encoding="utf-8")
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            match_result = MatchResult(
                candidate_id=media_candidate.id,
                media_type=MediaType.MOVIE,
                confidence=ConfidenceLevel.HIGH,
                title="Avatar",
                year=2009,
                tmdb_id=19995,
                metadata={"title": "Avatar", "release_year": 2009, "tmdb_id": 19995},
            )
            plan_items = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=match_result,
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )
            manager.start_identify(task.id)
            manager.mark_identified(
                task.id,
                candidate_matches={
                    media_candidate.id: CandidateMatch(
                        source_candidate_id=media_candidate.id,
                        confidence=ConfidenceLevel.HIGH,
                        metadata={"title": "Avatar", "release_year": 2009, "tmdb_id": 19995},
                        metadata_source="auto",
                    )
                },
                plan_items=plan_items,
            )
            set_plan_item_decision(manager.get(task.id), plan_items[0].id, CandidateDecision.ACCEPT)

            restarted = manager.restart_scan(task.id)

            self.assertEqual(restarted.state.value, "scanning")
            self.assertEqual(restarted.media_candidates, [])
            self.assertEqual(restarted.candidate_matches, {})
            self.assertEqual(restarted.plan_items, [])
            self.assertEqual(restarted.source_states, {})
            self.assertEqual(restarted.file_states, {})
            self.assertIsNone(restarted.last_source_action_outcome)

    def test_movie_folder_expansion_sets_source_candidate_ids_for_parts_and_subtitles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Avatar.2009"
            folder.mkdir()
            (folder / "Avatar.2009.CD1.mkv").write_text("disc 1", encoding="utf-8")
            (folder / "Avatar.2009.CD2.mkv").write_text("disc 2", encoding="utf-8")
            subtitle = folder / "Avatar.2009.zh.srt"
            subtitle.write_text("subtitle", encoding="utf-8")
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]

            candidates = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=MatchResult(
                    candidate_id=media_candidate.id,
                    media_type=MediaType.MOVIE,
                    confidence=ConfidenceLevel.HIGH,
                    title="Avatar",
                    year=2009,
                    tmdb_id=19995,
                    metadata={"title": "Avatar", "release_year": 2009, "tmdb_id": 19995},
                ),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )

            self.assertGreaterEqual(len(candidates), 3)
            self.assertTrue(any(candidate.source_path == subtitle for candidate in candidates))
            self.assertEqual({candidate.source_candidate_id for candidate in candidates}, {media_candidate.id})
            self.assertEqual(
                {candidate.source_file_id for candidate in candidates},
                {source_file_id(media_candidate.id, item.relative_path) for item in media_candidate.files if item.path in {candidate.source_path for candidate in candidates}},
            )

    def test_tv_show_expansion_sets_source_candidate_ids_for_episodes_and_subtitles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            show = root / "Example.Show"
            show.mkdir()
            (show / "Example.Show.S01E01.mkv").write_text("video", encoding="utf-8")
            subtitle = show / "Example.Show.S01E01.zh.srt"
            subtitle.write_text("subtitle", encoding="utf-8")
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]

            candidates = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=MatchResult(
                    candidate_id=media_candidate.id,
                    media_type=MediaType.TV,
                    confidence=ConfidenceLevel.HIGH,
                    title="Example Show",
                    year=2020,
                    tmdb_id=1,
                    metadata={"title": "Example Show", "release_year": 2020, "tmdb_id": 1},
                ),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )

            self.assertGreaterEqual(len(candidates), 2)
            self.assertTrue(any(candidate.source_path == subtitle for candidate in candidates))
            self.assertEqual({candidate.source_candidate_id for candidate in candidates}, {media_candidate.id})
            self.assertTrue(all(candidate.source_file_id.startswith("file_") for candidate in candidates))

    def test_tv_preview_uses_episode_file_extension_and_title(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            show = root / "Example Show (2020)"
            show.mkdir()
            episode = show / "Example.Show.S01E01.mkv"
            episode.write_text("x", encoding="utf-8")
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]
            match_result = MatchResult(
                candidate_id=media_candidate.id,
                media_type=MediaType.TV,
                confidence=ConfidenceLevel.HIGH,
                title="Example Show",
                year=2020,
                tmdb_id=1,
                metadata={
                    "title": "Example Show",
                    "release_year": 2020,
                    "tmdb_id": 1,
                    "episode_titles": {1: {1: "Pilot"}},
                },
            )

            candidates = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=match_result,
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )

            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0].source_path, episode)
            self.assertEqual(
                candidates[0].preview.proposed_relative_path,
                Path("Example Show (2020) {tmdb-1}/Season 1/Example Show - S01E01 - Pilot.mkv"),
            )

    def test_source_review_schema_exposes_inventory_classification_and_plan_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Avatar.2009"
            folder.mkdir()
            for name in [
                "Avatar.2009.CD1.mkv",
                "Avatar.2009.NoToken.mkv",
                "Avatar.2009.a.srt",
                "Avatar.2009.b.srt",
                "movie.nfo",
                "notes.json",
            ]:
                (folder / name).write_text("x", encoding="utf-8")
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            plan_items = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=MatchResult(
                    candidate_id=media_candidate.id,
                    media_type=MediaType.MOVIE,
                    confidence=ConfidenceLevel.HIGH,
                    title="Avatar",
                    year=2009,
                    tmdb_id=19995,
                    metadata={"title": "Avatar", "release_year": 2009, "tmdb_id": 19995},
                ),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )
            self._mark_identified(manager, task, media_candidate, plan_items)

            review = build_source_review_candidates(task, extensions=TEST_MEDIA_EXTENSIONS)[0]
            by_name = {file.relative_path.as_posix(): file for file in review.files}

            self.assertEqual(by_name["Avatar.2009.CD1.mkv"].classification, "video")
            self.assertEqual(by_name["Avatar.2009.CD1.mkv"].plan_status, "planned_primary")
            self.assertEqual(by_name["Avatar.2009.NoToken.mkv"].plan_status, "unplanned_extra_video")
            self.assertEqual(by_name["Avatar.2009.a.srt"].plan_status, "planned_subtitle")
            self.assertEqual(by_name["Avatar.2009.b.srt"].plan_status, "ignored_duplicate_subtitle")
            self.assertEqual(by_name["movie.nfo"].classification, "generic_sidecar")
            self.assertEqual(by_name["movie.nfo"].plan_status, "generic_sidecar_ignored")
            self.assertEqual(by_name["notes.json"].classification, "unsupported")
            self.assertEqual(by_name["notes.json"].plan_status, "unsupported")

    def test_conflict_reviews_include_unaccepted_plan_items_for_duplicate_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "A.2020.mkv").write_text("a", encoding="utf-8")
            (root / "B.2020.mkv").write_text("b", encoding="utf-8")
            media_candidates = sorted(scan_movie_root(root, TEST_MEDIA_EXTENSIONS), key=lambda item: item.display_name)
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, media_candidates)
            manager.start_identify(task.id)
            plan_items = []
            for index, media_candidate in enumerate(media_candidates):
                file = media_candidate.files[0]
                item = self._candidate(f"plan-{index}", ConfidenceLevel.HIGH, source_path=file.path)
                item.source_candidate_id = media_candidate.id
                item.source_file_id = source_file_id(media_candidate.id, file.relative_path)
                item.preview = CandidatePreview(proposed_relative_path=Path("Shared Movie (2020) {tmdb-1}/Shared Movie.mkv"))
                item.user_decision = CandidateDecision.ACCEPT if index == 0 else CandidateDecision.IGNORE
                plan_items.append(item)
            manager.mark_identified(
                task.id,
                candidate_matches={
                    media_candidate.id: CandidateMatch(source_candidate_id=media_candidate.id, confidence=ConfidenceLevel.HIGH)
                    for media_candidate in media_candidates
                },
                plan_items=plan_items,
            )
            ignored_source_id = media_candidates[1].id
            for item in manager.get(task.id).plan_items:
                if item.source_candidate_id == ignored_source_id:
                    item.user_decision = CandidateDecision.IGNORE

            review = build_source_review_candidates(manager.get(task.id), extensions=TEST_MEDIA_EXTENSIONS, target_depot=self._depot(root / "Depot"))

            accepted_review = next(candidate for candidate in review if candidate.id == media_candidates[0].id)
            unaccepted_review = next(candidate for candidate in review if candidate.id == media_candidates[1].id)
            self.assertEqual(len(accepted_review.conflict_reviews), 1)
            self.assertTrue(accepted_review.conflict_reviews[0].conflict)
            self.assertEqual(accepted_review.conflict_reviews[0].status, "duplicate_source")
            self.assertEqual(set(accepted_review.conflict_reviews[0].source_candidate_ids), {candidate.id for candidate in media_candidates})
            self.assertEqual(accepted_review.conflict_reviews[0].accepted_source_candidate_ids, [])
            self.assertEqual(len(unaccepted_review.conflict_reviews), 1)
            self.assertTrue(unaccepted_review.conflict_reviews[0].conflict)

    def test_conflict_reviews_are_hidden_for_incremental_tv_depot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            show = root / "Example.Show"
            show.mkdir()
            episode = show / "Example.Show.S01E01.mkv"
            episode.write_text("episode", encoding="utf-8")
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._tv_origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            file = media_candidate.files[0]
            item = self._candidate("tv-plan", ConfidenceLevel.HIGH, source_path=episode)
            item.source_candidate_id = media_candidate.id
            item.source_file_id = source_file_id(media_candidate.id, file.relative_path)
            item.preview = CandidatePreview(
                proposed_relative_path=Path("Example Show (2020) {tmdb-1}/Season 1/Example Show - S01E01 - Pilot.mkv")
            )
            item.evidence = {TV_EPISODE_PLAN_EVIDENCE_KEY: {"season": 1, "episode": 1, "end_episode": None}}
            item.user_decision = CandidateDecision.ACCEPT
            manager.mark_identified(
                task.id,
                candidate_matches={media_candidate.id: CandidateMatch(source_candidate_id=media_candidate.id, confidence=ConfidenceLevel.HIGH)},
                plan_items=[item],
            )
            incremental_depot = replace(self._tv_depot(root / "Depot"), resolve_mode=ResolveMode.INCREMENTAL)

            review = build_source_review_candidates(manager.get(task.id), extensions=TEST_MEDIA_EXTENSIONS, target_depot=incremental_depot)

            self.assertEqual(review[0].conflict_reviews, [])

    def test_duplicate_conflict_review_defaults_off_and_keep_switches_winner(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "A.2020.mkv").write_text("a", encoding="utf-8")
            (root / "B.2020.mkv").write_text("b", encoding="utf-8")
            media_candidates = sorted(scan_movie_root(root, TEST_MEDIA_EXTENSIONS), key=lambda item: item.display_name)
            depot = self._depot(root / "Depot")
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, media_candidates)
            manager.start_identify(task.id)
            plan_items = []
            for index, media_candidate in enumerate(media_candidates):
                file = media_candidate.files[0]
                item = self._candidate(f"plan-{index}", ConfidenceLevel.HIGH, source_path=file.path)
                item.source_candidate_id = media_candidate.id
                item.source_file_id = source_file_id(media_candidate.id, file.relative_path)
                item.preview = CandidatePreview(proposed_relative_path=Path("Shared Movie (2020) {tmdb-1}/Shared Movie.mkv"))
                plan_items.append(item)
            manager.mark_identified(
                task.id,
                candidate_matches={
                    media_candidate.id: CandidateMatch(source_candidate_id=media_candidate.id, confidence=ConfidenceLevel.HIGH)
                    for media_candidate in media_candidates
                },
                plan_items=plan_items,
                target_depot=depot,
            )
            identity_key = package_identity(manager.get(task.id).plan_items[0], MediaType.MOVIE).key

            self.assertTrue(all(item.user_decision is None for item in manager.get(task.id).plan_items))

            apply_conflict_review_action(
                manager.get(task.id),
                identity_key=identity_key,
                source_candidate_id=media_candidates[0].id,
                action="keep",
                target_depot=depot,
            )
            by_source = {item.source_candidate_id: item.user_decision for item in manager.get(task.id).plan_items}
            self.assertEqual(by_source[media_candidates[0].id], CandidateDecision.ACCEPT)
            self.assertIsNone(by_source[media_candidates[1].id])

            apply_conflict_review_action(
                manager.get(task.id),
                identity_key=identity_key,
                source_candidate_id=media_candidates[1].id,
                action="keep",
                target_depot=depot,
            )
            by_source = {item.source_candidate_id: item.user_decision for item in manager.get(task.id).plan_items}
            self.assertIsNone(by_source[media_candidates[0].id])
            self.assertEqual(by_source[media_candidates[1].id], CandidateDecision.ACCEPT)

    def test_target_exists_requires_replace_action_before_accept(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "Avatar.2009.mkv"
            source.write_text("new", encoding="utf-8")
            depot = self._depot(root / "Depot")
            package_root = depot.path / "Avatar (2009) {tmdb-19995}"
            package_root.mkdir(parents=True)
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            item = self._candidate("movie", ConfidenceLevel.HIGH, source_path=source)
            item.source_candidate_id = media_candidate.id
            item.source_file_id = source_file_id(media_candidate.id, media_candidate.files[0].relative_path)
            item.preview = CandidatePreview(proposed_relative_path=Path("Avatar (2009) {tmdb-19995}/Avatar.2009.mkv"))
            manager.mark_identified(
                task.id,
                candidate_matches={media_candidate.id: CandidateMatch(source_candidate_id=media_candidate.id, confidence=ConfidenceLevel.HIGH)},
                plan_items=[item],
                target_depot=depot,
            )
            identity_key = package_identity(manager.get(task.id).plan_items[0], MediaType.MOVIE).key

            self.assertIsNone(manager.get(task.id).plan_items[0].user_decision)
            with self.assertRaises(Exception):
                set_plan_item_decision(manager.get(task.id), item.id, CandidateDecision.ACCEPT, target_depot=depot)

            apply_conflict_review_action(
                manager.get(task.id),
                identity_key=identity_key,
                source_candidate_id=media_candidate.id,
                action="replace_target",
                target_depot=depot,
            )

            self.assertEqual(manager.get(task.id).plan_items[0].user_decision, CandidateDecision.ACCEPT)
            set_plan_item_decision(manager.get(task.id), item.id, CandidateDecision.IGNORE, target_depot=depot)
            validate_accepted_conflict_scope(manager.get(task.id), target_depot=depot)

    def test_target_exists_tag_variant_uses_tagged_movie_root_not_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "Avatar.2009.mkv"
            source.write_text("new", encoding="utf-8")
            depot = self._depot(root / "Depot")
            bucket = depot.path / "Movies"
            package_root = bucket / "Avatar (2009) {tmdb-19995}"
            package_root.mkdir(parents=True)
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            item = self._candidate("movie", ConfidenceLevel.HIGH, source_path=source)
            item.source_candidate_id = media_candidate.id
            item.source_file_id = source_file_id(media_candidate.id, media_candidate.files[0].relative_path)
            item.preview = CandidatePreview(proposed_relative_path=Path("Movies/Avatar (2009) {tmdb-19995}/Avatar.2009.mkv"))
            manager.mark_identified(
                task.id,
                candidate_matches={media_candidate.id: CandidateMatch(source_candidate_id=media_candidate.id, confidence=ConfidenceLevel.HIGH)},
                plan_items=[item],
                target_depot=depot,
            )
            identity_key = package_identity(manager.get(task.id).plan_items[0], MediaType.MOVIE).key

            apply_conflict_review_action(
                manager.get(task.id),
                identity_key=identity_key,
                source_candidate_id=media_candidate.id,
                action="tag_variant",
                tag_override="WEB",
                target_depot=depot,
            )

            updated_item = manager.get(task.id).plan_items[0]
            self.assertEqual(updated_item.user_decision, CandidateDecision.ACCEPT)
            self.assertEqual(
                updated_item.preview.proposed_relative_path,
                Path("Movies/Avatar (2009) {tmdb-19995} [WEB]/Avatar.2009.mkv"),
            )

    def test_tag_variant_after_replace_target_clears_replace_intent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "Avatar.2009.mkv"
            source.write_text("new", encoding="utf-8")
            depot = self._depot(root / "Depot")
            package_root = depot.path / "Avatar (2009) {tmdb-19995}"
            package_root.mkdir(parents=True)
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            item = self._candidate("movie", ConfidenceLevel.HIGH, source_path=source)
            item.source_candidate_id = media_candidate.id
            item.source_file_id = source_file_id(media_candidate.id, media_candidate.files[0].relative_path)
            item.preview = CandidatePreview(proposed_relative_path=Path("Avatar (2009) {tmdb-19995}/Avatar.2009.mkv"))
            manager.mark_identified(
                task.id,
                candidate_matches={media_candidate.id: CandidateMatch(source_candidate_id=media_candidate.id, confidence=ConfidenceLevel.HIGH)},
                plan_items=[item],
                target_depot=depot,
            )
            identity_key = package_identity(manager.get(task.id).plan_items[0], MediaType.MOVIE).key

            apply_conflict_review_action(
                manager.get(task.id),
                identity_key=identity_key,
                source_candidate_id=media_candidate.id,
                action="replace_target",
                target_depot=depot,
            )
            self.assertTrue(manager.get(task.id).conflict_review_states[identity_key].replace)

            apply_conflict_review_action(
                manager.get(task.id),
                identity_key=identity_key,
                source_candidate_id=media_candidate.id,
                action="tag_variant",
                tag_override="WEB",
                target_depot=depot,
            )

            updated_item = manager.get(task.id).plan_items[0]
            new_identity_key = package_identity(updated_item, MediaType.MOVIE).key
            self.assertEqual(updated_item.user_decision, CandidateDecision.ACCEPT)
            self.assertEqual(updated_item.preview.proposed_relative_path, Path("Avatar (2009) {tmdb-19995} [WEB]/Avatar.2009.mkv"))
            self.assertNotEqual(new_identity_key, identity_key)
            self.assertNotIn(identity_key, manager.get(task.id).conflict_review_states)
            validate_accepted_conflict_scope(manager.get(task.id), target_depot=depot)

    def test_tag_variant_collision_preserves_previous_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "A.2020.mkv").write_text("a", encoding="utf-8")
            (root / "B.2020.mkv").write_text("b", encoding="utf-8")
            media_candidates = sorted(scan_movie_root(root, TEST_MEDIA_EXTENSIONS), key=lambda item: item.display_name)
            depot = self._depot(root / "Depot")
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, media_candidates)
            manager.start_identify(task.id)
            plan_items = []
            for index, media_candidate in enumerate(media_candidates):
                file = media_candidate.files[0]
                item = self._candidate(f"plan-{index}", ConfidenceLevel.HIGH, source_path=file.path)
                item.source_candidate_id = media_candidate.id
                item.source_file_id = source_file_id(media_candidate.id, file.relative_path)
                item.preview = CandidatePreview(proposed_relative_path=Path("Shared Movie (2020) {tmdb-1}/Shared Movie.mkv"))
                plan_items.append(item)
            manager.mark_identified(
                task.id,
                candidate_matches={
                    media_candidate.id: CandidateMatch(source_candidate_id=media_candidate.id, confidence=ConfidenceLevel.HIGH)
                    for media_candidate in media_candidates
                },
                plan_items=plan_items,
                target_depot=depot,
            )
            identity_key = package_identity(manager.get(task.id).plan_items[0], MediaType.MOVIE).key

            apply_conflict_review_action(
                manager.get(task.id),
                identity_key=identity_key,
                source_candidate_id=media_candidates[0].id,
                action="tag_variant",
                tag_override="WEB",
                target_depot=depot,
            )
            with self.assertRaises(Exception):
                apply_conflict_review_action(
                    manager.get(task.id),
                    identity_key=identity_key,
                    source_candidate_id=media_candidates[1].id,
                    action="tag_variant",
                    tag_override="WEB",
                    target_depot=depot,
                )

            first_item = next(item for item in manager.get(task.id).plan_items if item.source_candidate_id == media_candidates[0].id)
            second_item = next(item for item in manager.get(task.id).plan_items if item.source_candidate_id == media_candidates[1].id)
            self.assertIn("WEB", first_item.preview.proposed_relative_path.parts[0])
            self.assertEqual(first_item.user_decision, CandidateDecision.ACCEPT)
            self.assertNotIn("WEB", second_item.preview.proposed_relative_path.parts[0])
            self.assertIsNone(second_item.user_decision)

    def test_identified_conflict_candidate_file_operations_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "A.2020.mkv").write_text("a", encoding="utf-8")
            (root / "B.2020.mkv").write_text("b", encoding="utf-8")
            media_candidates = sorted(scan_movie_root(root, TEST_MEDIA_EXTENSIONS), key=lambda item: item.display_name)
            depot = self._depot(root / "Depot")
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, media_candidates)
            manager.start_identify(task.id)
            plan_items = []
            for index, media_candidate in enumerate(media_candidates):
                file = media_candidate.files[0]
                item = self._candidate(f"plan-{index}", ConfidenceLevel.HIGH, source_path=file.path)
                item.source_candidate_id = media_candidate.id
                item.source_file_id = source_file_id(media_candidate.id, file.relative_path)
                item.preview = CandidatePreview(proposed_relative_path=Path("Shared Movie (2020) {tmdb-1}/Shared Movie.mkv"))
                plan_items.append(item)
            manager.mark_identified(
                task.id,
                candidate_matches={
                    media_candidate.id: CandidateMatch(source_candidate_id=media_candidate.id, confidence=ConfidenceLevel.HIGH)
                    for media_candidate in media_candidates
                },
                plan_items=plan_items,
                target_depot=depot,
            )
            file_id = source_file_id(media_candidates[0].id, media_candidates[0].files[0].relative_path)
            identity_key = package_identity(manager.get(task.id).plan_items[0], MediaType.MOVIE).key

            with self.assertRaises(Exception):
                self._source_edit(manager, task.id, media_candidates[0].id, target_depot=depot).rename_file(file_id, "Renamed.mkv")
            with self.assertRaises(Exception):
                self._source_edit(manager, task.id, media_candidates[0].id, target_depot=depot).delete_file(file_id)
            apply_conflict_review_action(
                manager.get(task.id),
                identity_key=identity_key,
                source_candidate_id=media_candidates[1].id,
                action="keep",
                target_depot=depot,
            )

            updated = self._source_edit(manager, task.id, media_candidates[1].id, target_depot=depot).delete_candidate()

            self.assertFalse((root / "B.2020.mkv").exists())
            self.assertEqual([item.source_candidate_id for item in updated.plan_items], [media_candidates[0].id])
            self.assertIsNone(updated.plan_items[0].user_decision)
            self.assertNotIn(identity_key, updated.conflict_review_states)
            remaining = next(item for item in build_source_review_candidates(updated, extensions=TEST_MEDIA_EXTENSIONS, target_depot=depot) if item.id == media_candidates[0].id)
            self.assertEqual(remaining.conflict_reviews[0].status, "ready")
            self.assertFalse(remaining.conflict_reviews[0].action_required)

    def test_source_file_detail_and_delete_update_session_without_rescan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Avatar.2009"
            folder.mkdir()
            video = folder / "Avatar.2009.mkv"
            subtitle = folder / "Avatar.2009.zh.srt"
            video.write_text("video", encoding="utf-8")
            subtitle.write_text("subtitle", encoding="utf-8")
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            plan_items = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=MatchResult(
                    candidate_id=media_candidate.id,
                    media_type=MediaType.MOVIE,
                    confidence=ConfidenceLevel.HIGH,
                    title="Avatar",
                    year=2009,
                    tmdb_id=19995,
                    metadata={"title": "Avatar", "release_year": 2009, "tmdb_id": 19995},
                ),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )
            self._mark_identified(manager, task, media_candidate, plan_items)
            subtitle_file = next(file for file in media_candidate.files if file.path == subtitle)
            subtitle_file_id = source_file_id(media_candidate.id, subtitle_file.relative_path)

            candidate_detail = source_candidate_detail(manager.get(task.id), media_candidate.id)
            self.assertTrue(candidate_detail.exists)
            self.assertEqual(candidate_detail.file_type, "directory")
            self.assertIsNotNone(candidate_detail.created_time)
            self.assertIsNotNone(candidate_detail.modified_time)

            detail = source_file_detail(
                manager.get(task.id),
                media_candidate.id,
                subtitle_file_id,
                extensions=TEST_MEDIA_EXTENSIONS,
            )
            self.assertTrue(detail["exists"])
            self.assertEqual(detail["classification"], "subtitle")

            updated = self._source_edit(manager, task.id, media_candidate.id).delete_file(subtitle_file_id)

            self.assertFalse(subtitle.exists())
            self.assertEqual(updated.file_states[subtitle_file_id].status.value, "deleted")
            self.assertTrue(any(item.source_path == video for item in updated.plan_items))
            self.assertFalse(any(item.source_path == subtitle for item in updated.plan_items))

    def test_source_file_rename_remaps_file_state_and_plan_item_after_identify(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie = root / "Avatar.mkv"
            movie.write_text("video", encoding="utf-8")
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            plan_items = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=MatchResult(
                    candidate_id=media_candidate.id,
                    media_type=MediaType.MOVIE,
                    confidence=ConfidenceLevel.HIGH,
                    title="Avatar",
                    year=2009,
                    tmdb_id=19995,
                    metadata={"title": "Avatar", "release_year": 2009, "tmdb_id": 19995},
                ),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )
            self._mark_identified(manager, task, media_candidate, plan_items)
            old_file = media_candidate.files[0]
            old_file_id = source_file_id(media_candidate.id, old_file.relative_path)
            set_plan_item_decision(manager.get(task.id), plan_items[0].id, CandidateDecision.ACCEPT)

            updated = self._source_edit(manager, task.id, media_candidate.id).rename_file(old_file_id, "Avatar.2009.mkv")

            new_path = root / "Avatar.2009.mkv"
            new_file = updated.media_candidates[0].files[0]
            new_file_id = source_file_id(media_candidate.id, Path("Avatar.2009.mkv"))
            updated_item = next(item for item in updated.plan_items if item.source_file_id == new_file_id)
            self.assertFalse(movie.exists())
            self.assertTrue(new_path.exists())
            self.assertEqual(updated.media_candidates[0].id, media_candidate.id)
            self.assertEqual(updated.media_candidates[0].candidate_path, new_path)
            self.assertEqual(new_file.path, new_path)
            self.assertEqual(new_file.relative_path, Path("Avatar.2009.mkv"))
            self.assertNotIn(old_file_id, updated.file_states)
            self.assertIn(new_file_id, updated.file_states)
            self.assertEqual(updated_item.source_path, new_path)
            self.assertEqual(updated_item.user_decision, CandidateDecision.ACCEPT)
            self.assertEqual(updated.last_source_action_outcome.old_source_file_id, old_file_id)
            self.assertEqual(updated.last_source_action_outcome.new_source_file_id, new_file_id)

    def test_source_file_rename_before_identify_updates_inventory_for_later_identify(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie = root / "Avatar.mkv"
            movie.write_text("video", encoding="utf-8")
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            old_file_id = source_file_id(media_candidate.id, Path("Avatar.mkv"))

            updated = self._source_edit(manager, task.id, media_candidate.id).rename_file(old_file_id, "Avatar.2009.mkv")

            new_file = updated.media_candidates[0].files[0]
            new_file_id = source_file_id(media_candidate.id, Path("Avatar.2009.mkv"))
            self.assertEqual(updated.state.value, "scanned")
            self.assertEqual(updated.plan_items, [])
            self.assertEqual(new_file.path, root / "Avatar.2009.mkv")
            self.assertIn(new_file_id, updated.file_states)
            self.assertNotIn(old_file_id, updated.file_states)

    def test_source_candidate_folder_rename_preserves_candidate_id_and_child_file_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Avatar"
            folder.mkdir()
            (folder / "Avatar.mkv").write_text("video", encoding="utf-8")
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            old_file_ids = {source_file_id(media_candidate.id, file.relative_path) for file in media_candidate.files}
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            plan_items = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=MatchResult(
                    candidate_id=media_candidate.id,
                    media_type=MediaType.MOVIE,
                    confidence=ConfidenceLevel.HIGH,
                    title="Avatar",
                    year=2009,
                    tmdb_id=19995,
                    metadata={"title": "Avatar", "release_year": 2009, "tmdb_id": 19995},
                ),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )
            self._mark_identified(manager, task, media_candidate, plan_items)

            updated = self._source_edit(manager, task.id, media_candidate.id).rename_candidate("Avatar.2009")

            renamed = updated.media_candidates[0]
            new_folder = root / "Avatar.2009"
            self.assertEqual(renamed.id, media_candidate.id)
            self.assertEqual(renamed.candidate_path, new_folder)
            self.assertEqual(renamed.display_name, "Avatar.2009")
            self.assertEqual({source_file_id(renamed.id, file.relative_path) for file in renamed.files}, old_file_ids)
            self.assertTrue(all(file.path.is_relative_to(new_folder) for file in renamed.files))
            self.assertTrue(all(item.source_path.is_relative_to(new_folder) for item in updated.plan_items))

    def test_tv_show_candidate_rename_preserves_candidate_id_and_child_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            show = root / "Example.Show"
            show.mkdir()
            (show / "Example.Show.S01E01.mkv").write_text("video", encoding="utf-8")
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]
            old_file_ids = {source_file_id(media_candidate.id, file.relative_path) for file in media_candidate.files}
            manager = SessionBook()
            task = manager.create_for_origin(self._tv_origin(root))
            manager.mark_scanned(task.id, [media_candidate])

            updated = self._source_edit(manager, task.id, media_candidate.id).rename_candidate("Example Show")

            renamed = updated.media_candidates[0]
            new_folder = root / "Example Show"
            self.assertEqual(renamed.id, media_candidate.id)
            self.assertEqual(renamed.candidate_path, new_folder)
            self.assertEqual({source_file_id(renamed.id, file.relative_path) for file in renamed.files}, old_file_ids)
            self.assertTrue(all(file.path.is_relative_to(new_folder) for file in renamed.files))

    def test_rename_preserves_unrelated_decisions_and_clears_stale_affected_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "Avatar.mkv"
            second = root / "Arrival.mkv"
            first.write_text("first", encoding="utf-8")
            second.write_text("second", encoding="utf-8")
            media_candidates = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)
            first_candidate = next(candidate for candidate in media_candidates if candidate.candidate_path == first)
            second_candidate = next(candidate for candidate in media_candidates if candidate.candidate_path == second)
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, media_candidates)
            manager.start_identify(task.id)
            plan_items = []
            matches = {}
            for candidate in media_candidates:
                match = MatchResult(
                    candidate_id=candidate.id,
                    media_type=MediaType.MOVIE,
                    confidence=ConfidenceLevel.HIGH,
                    title=candidate.display_name,
                    year=2009,
                    tmdb_id=19995,
                    metadata={"title": candidate.display_name, "release_year": 2009, "tmdb_id": 19995},
                )
                plan_items.extend(
                    Preview.for_candidate(
                        media_candidate=candidate,
                        source_root=root,
                        match_result=match,
                        policy=OrganizePolicy(target_depot_id="Depot"),
                        extensions=TEST_MEDIA_EXTENSIONS,
                    )
                )
                matches[candidate.id] = CandidateMatch(
                    source_candidate_id=candidate.id,
                    confidence=ConfidenceLevel.HIGH,
                    metadata={"title": candidate.display_name, "release_year": 2009, "tmdb_id": 19995},
                    metadata_source="auto",
                )
            manager.mark_identified(task.id, candidate_matches=matches, plan_items=plan_items)
            second_item = next(item for item in task.plan_items if item.source_candidate_id == second_candidate.id)
            first_item = next(item for item in task.plan_items if item.source_candidate_id == first_candidate.id)
            set_plan_item_decision(manager.get(task.id), second_item.id, CandidateDecision.ACCEPT)
            set_plan_item_decision(manager.get(task.id), first_item.id, CandidateDecision.ACCEPT)
            first_file_id = source_file_id(first_candidate.id, Path("Avatar.mkv"))

            updated = self._source_edit(manager, task.id, first_candidate.id).rename_file(first_file_id, "Avatar.txt")

            unrelated = next(item for item in updated.plan_items if item.source_candidate_id == second_candidate.id)
            self.assertEqual(unrelated.user_decision, CandidateDecision.ACCEPT)
            self.assertEqual(unrelated.source_path, second)
            self.assertNotIn(first_candidate.id, {item.source_candidate_id for item in updated.plan_items})
            self.assertEqual(updated.source_states[first_candidate.id].status.value, "unavailable")

    def test_source_candidate_delete_removes_tree_and_plan_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Avatar.2009"
            folder.mkdir()
            (folder / "Avatar.2009.mkv").write_text("video", encoding="utf-8")
            (folder / "notes.json").write_text("notes", encoding="utf-8")
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            plan_items = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=MatchResult(
                    candidate_id=media_candidate.id,
                    media_type=MediaType.MOVIE,
                    confidence=ConfidenceLevel.HIGH,
                    title="Avatar",
                    year=2009,
                    tmdb_id=19995,
                    metadata={"title": "Avatar", "release_year": 2009, "tmdb_id": 19995},
                ),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )
            self._mark_identified(manager, task, media_candidate, plan_items)

            updated = self._source_edit(manager, task.id, media_candidate.id).delete_candidate()

            self.assertFalse(folder.exists())
            self.assertEqual(updated.source_states[media_candidate.id].status.value, "deleted")
            self.assertEqual(updated.plan_items, [])

    def test_source_candidate_delete_blocks_link_or_reparse_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Avatar.2009"
            linked = root / "linked"
            folder.mkdir()
            linked.mkdir()
            (folder / "Avatar.2009.mkv").write_text("video", encoding="utf-8")
            try:
                (folder / "linked").symlink_to(linked, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, [media_candidate])

            with self.assertRaises(Exception):
                self._source_edit(manager, task.id, media_candidate.id).delete_candidate()

            self.assertTrue(folder.exists())

    def test_tv_manual_override_preserves_planned_folder_season(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            show = root / "The.Outcast.S02"
            show.mkdir()
            episode = show / "E01.mkv"
            episode.write_text("x", encoding="utf-8")
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._tv_origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            candidates = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=MatchResult(
                    candidate_id=media_candidate.id,
                    media_type=MediaType.TV,
                    confidence=ConfidenceLevel.HIGH,
                    title="Old Show",
                    year=2020,
                    tmdb_id=1,
                    metadata={"title": "Old Show", "release_year": 2020, "tmdb_id": 1},
                ),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )
            self._mark_identified(manager, task, media_candidate, candidates)

            updated = apply_source_candidate_tmdb_override(
                manager.get(task.id),
                media_candidate.id,
                tmdb_id=2,
                tmdb_client=_FakeTMDBOverride(),
            )
            updated_item = next(item for item in updated.plan_items if item.source_path == episode)

            self.assertEqual(updated_item.source_path, episode)
            self.assertEqual(
                updated_item.preview.proposed_relative_path,
                Path("Override Show (2021) {tmdb-2}/Season 2/Override Show - S02E01 - Override Pilot.mkv"),
            )
            self.assertEqual(updated_item.evidence[TV_EPISODE_PLAN_EVIDENCE_KEY]["episode_title"], "Override Pilot")
            self.assertEqual(updated_item.evidence[TV_EPISODE_PLAN_EVIDENCE_KEY]["episode_title_source"], "metadata")

    def test_tv_manual_override_rebuilds_plan_items_with_episode_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            show = root / "Example.Show"
            show.mkdir()
            episode = show / "S01E01.mkv"
            episode.write_text("x", encoding="utf-8")
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._tv_origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            candidates = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=MatchResult(
                    candidate_id=media_candidate.id,
                    media_type=MediaType.TV,
                    confidence=ConfidenceLevel.HIGH,
                    title="Old Show",
                    year=2020,
                    tmdb_id=1,
                    metadata={"title": "Old Show", "release_year": 2020, "tmdb_id": 1},
                ),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )
            self._mark_identified(manager, task, media_candidate, candidates)
            original_item = next(item for item in task.plan_items if item.source_path == episode)
            self.assertIsNone(original_item.evidence[TV_EPISODE_PLAN_EVIDENCE_KEY]["episode_title"])

            service = TVEpisodePlanner(
                extensions=TEST_MEDIA_EXTENSIONS,
                episode_extractor=FakeTVEpisodeExtractor(),
                episode_catalog_provider=FakeTVEpisodeCatalogProvider(TVEpisodeCatalog({1: {1: "Catalog Pilot"}})),
            )
            updated = apply_source_candidate_tmdb_override(
                manager.get(task.id),
                media_candidate.id,
                tmdb_id=2,
                tmdb_client=_CatalogOnlyTMDBOverride(),
                tv_episode_planner=service,
            )
            updated_item = next(item for item in updated.plan_items if item.source_path == episode)

            self.assertEqual(updated_item.evidence[TV_EPISODE_PLAN_EVIDENCE_KEY]["episode_title"], "Catalog Pilot")
            self.assertEqual(updated_item.evidence[TV_EPISODE_PLAN_EVIDENCE_KEY]["episode_title_source"], "tmdb_catalog")
            self.assertEqual(
                updated_item.preview.proposed_relative_path,
                Path("Override Show (2021) {tmdb-2}/Season 1/Override Show - S01E01 - Catalog Pilot.mkv"),
            )

    def test_tv_manual_override_preserves_resolution_plan_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            show = root / "Example.Show"
            show.mkdir()
            episode = show / "UglyNameA.mkv"
            episode.write_text("x", encoding="utf-8")
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]
            service = TVEpisodePlanner(
                extensions=TEST_MEDIA_EXTENSIONS,
                episode_extractor=FakeTVEpisodeExtractor(
                    {"UglyNameA.mkv": {"season": 2, "episode": 7, "end_episode": None}}
                ),
                episode_catalog_provider=FakeTVEpisodeCatalogProvider(TVEpisodeCatalog({2: {7: "Old Corrected"}})),
            )
            manager = SessionBook()
            task = manager.create_for_origin(self._tv_origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            candidates = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=MatchResult(
                    candidate_id=media_candidate.id,
                    media_type=MediaType.TV,
                    confidence=ConfidenceLevel.HIGH,
                    title="Old Show",
                    year=2020,
                    tmdb_id=1,
                    metadata={"title": "Old Show", "release_year": 2020, "tmdb_id": 1},
                ),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
                tv_episode_planner=service,
            )
            self._mark_identified(manager, task, media_candidate, candidates)

            updated = apply_source_candidate_tmdb_override(
                manager.get(task.id),
                media_candidate.id,
                tmdb_id=2,
                tmdb_client=_FallbackTMDBOverride(),
            )
            updated_item = next(item for item in updated.plan_items if item.source_path == episode)

            self.assertEqual(updated_item.source_path, episode)
            self.assertEqual(updated_item.evidence["tv_episode_plan"]["resolution"]["status"], "applied")
            self.assertEqual(
                updated_item.preview.proposed_relative_path,
                Path("Override Show (2021) {tmdb-2}/Season 2/Override Show - S02E07 - Override Corrected.mkv"),
            )

    def test_identify_uses_tv_episode_planner(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            show = root / "Example.Show"
            show.mkdir()
            (show / "UglyNameA.mkv").write_text("x", encoding="utf-8")
            manager = SessionBook()
            task = manager.create_for_origin(self._tv_origin(root))
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager.mark_scanned(task.id, [media_candidate])
            matcher = _FallbackTVMatcher()

            identified = run_identify_phase(
                manager,
                task.id,
                matcher=matcher,
                extensions=TEST_MEDIA_EXTENSIONS,
            )

            self.assertEqual(matcher.extractor.requested_keys, ["UglyNameA.mkv"])
            self.assertEqual(
                identified.candidates[0].preview.proposed_relative_path,
                Path("Example Show (2020) {tmdb-1}/Season 2/Example Show - S02E07 - Corrected.mkv"),
            )

    def test_tv_manual_override_preserves_subtitle_plan_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            show = root / "The.Outcast.S02"
            show.mkdir()
            (show / "E01.mkv").write_text("video", encoding="utf-8")
            subtitle = show / "E01.zh.srt"
            subtitle.write_text("x", encoding="utf-8")
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._tv_origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            candidates = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=MatchResult(
                    candidate_id=media_candidate.id,
                    media_type=MediaType.TV,
                    confidence=ConfidenceLevel.HIGH,
                    title="Old Show",
                    year=2020,
                    tmdb_id=1,
                    metadata={"title": "Old Show", "release_year": 2020, "tmdb_id": 1},
                ),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )
            self._mark_identified(manager, task, media_candidate, candidates)

            updated = apply_source_candidate_tmdb_override(
                manager.get(task.id),
                media_candidate.id,
                tmdb_id=2,
                tmdb_client=_FakeTMDBOverride(),
            )
            updated_item = next(item for item in updated.plan_items if item.source_path == subtitle)

            self.assertEqual(updated_item.source_path, subtitle)
            self.assertEqual(updated_item.evidence["tv_episode_plan"]["media_kind"], "subtitle")
            self.assertEqual(
                updated_item.preview.proposed_relative_path,
                Path("Override Show (2021) {tmdb-2}/Season 2/Override Show - S02E01 - Override Pilot.srt"),
            )

    def test_organize_moves_tv_subtitle_and_records_plan_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            try:
                show = root / "The.Outcast.S02"
                show.mkdir()
                (show / "E01.mkv").write_text("video", encoding="utf-8")
                subtitle = show / "E01.zh.srt"
                subtitle.write_text("subtitle", encoding="utf-8")
                media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]
                candidates = Preview.for_candidate(
                    media_candidate=media_candidate,
                    source_root=root,
                    match_result=MatchResult(
                        candidate_id=media_candidate.id,
                        media_type=MediaType.TV,
                        confidence=ConfidenceLevel.HIGH,
                        title="Example Show",
                        year=2020,
                        tmdb_id=1,
                        metadata={"title": "Example Show", "release_year": 2020, "tmdb_id": 1},
                    ),
                    policy=OrganizePolicy(target_depot_id="Depot"),
                    extensions=TEST_MEDIA_EXTENSIONS,
                )
                subtitle_candidate = next(item for item in candidates if item.source_path == subtitle)
                subtitle_candidate.user_decision = CandidateDecision.ACCEPT

                result = self._organizer(store).organize_candidate(
                    subtitle_candidate,
                    self._tv_depot(root / "Depot"),
                    source_root=root,
                )

                self.assertEqual(result.status, ResultStatus.SUCCEEDED)
                self.assertTrue((root / "Depot" / "Example Show (2020) {tmdb-1}" / "Season 2" / "Example Show - S02E01.srt").exists())
                context = store.list_activity_events()[0].context
                self.assertEqual(context["media_kind"], "subtitle")
                self.assertEqual(context["tv_planned_season"], 2)
                self.assertEqual(context["tv_planned_episode"], 1)
                self.assertEqual(context["planned_extension"], ".srt")
            finally:
                store.close()

    def test_organize_moves_movie_subtitle_and_records_plan_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            try:
                folder = root / "Avatar.2009"
                folder.mkdir()
                (folder / "Avatar.2009.mkv").write_text("video", encoding="utf-8")
                subtitle = folder / "Avatar.2009.zh.srt"
                subtitle.write_text("subtitle", encoding="utf-8")
                media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
                candidates = Preview.for_candidate(
                    media_candidate=media_candidate,
                    source_root=root,
                    match_result=MatchResult(
                        candidate_id=media_candidate.id,
                        media_type=MediaType.MOVIE,
                        confidence=ConfidenceLevel.HIGH,
                        title="Avatar",
                        year=2009,
                        tmdb_id=19995,
                        metadata={"title": "Avatar", "release_year": 2009, "tmdb_id": 19995},
                    ),
                    policy=OrganizePolicy(target_depot_id="Depot"),
                    extensions=TEST_MEDIA_EXTENSIONS,
                )
                subtitle_candidate = next(item for item in candidates if item.source_path == subtitle)
                subtitle_candidate.user_decision = CandidateDecision.ACCEPT

                result = self._organizer(store).organize_candidate(
                    subtitle_candidate,
                    self._depot(root / "Depot"),
                    source_root=root,
                )

                self.assertEqual(result.status, ResultStatus.SUCCEEDED)
                self.assertTrue((root / "Depot" / "Avatar (2009) {tmdb-19995}" / "Avatar (2009).srt").exists())
                context = store.list_activity_events()[0].context
                self.assertEqual(context["media_kind"], "subtitle")
                self.assertEqual(context["movie_primary_source"], "Avatar.2009.mkv")
                self.assertEqual(context["planned_extension"], ".srt")
            finally:
                store.close()

    def test_organize_moves_tokenized_movie_primary_and_records_part_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = self._store(root)
            try:
                folder = root / "Avatar.2009"
                folder.mkdir()
                (folder / "Avatar.2009.CD1.mkv").write_text("disc 1", encoding="utf-8")
                cd2 = folder / "Avatar.2009.CD2.mkv"
                cd2.write_text("disc 2", encoding="utf-8")
                media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
                candidates = Preview.for_candidate(
                    media_candidate=media_candidate,
                    source_root=root,
                    match_result=MatchResult(
                        candidate_id=media_candidate.id,
                        media_type=MediaType.MOVIE,
                        confidence=ConfidenceLevel.HIGH,
                        title="Avatar",
                        year=2009,
                        tmdb_id=19995,
                        metadata={"title": "Avatar", "release_year": 2009, "tmdb_id": 19995},
                    ),
                    policy=OrganizePolicy(target_depot_id="Depot"),
                    extensions=TEST_MEDIA_EXTENSIONS,
                )
                cd2_candidate = next(item for item in candidates if item.source_path == cd2)
                cd2_candidate.user_decision = CandidateDecision.ACCEPT

                result = self._organizer(store).organize_candidate(
                    cd2_candidate,
                    self._depot(root / "Depot"),
                    source_root=root,
                )

                self.assertEqual(result.status, ResultStatus.SUCCEEDED)
                self.assertTrue(
                    (root / "Depot" / "Avatar (2009) {tmdb-19995}" / "Avatar (2009) - CD2.mkv").exists()
                )
                context = store.list_activity_events()[0].context
                self.assertEqual(context["media_kind"], "primary")
                self.assertEqual(context["movie_primary_source"], "Avatar.2009.CD2.mkv")
                self.assertEqual(context["movie_part_token"], "CD2")
                self.assertEqual(context["planned_extension"], ".mkv")
            finally:
                store.close()

    def test_movie_manual_override_preserves_part_token_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Avatar.2009"
            folder.mkdir()
            (folder / "Avatar.2009.CD1.mkv").write_text("disc 1", encoding="utf-8")
            (folder / "Avatar.2009.CD2.mkv").write_text("disc 2", encoding="utf-8")
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            candidates = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=MatchResult(
                    candidate_id=media_candidate.id,
                    media_type=MediaType.MOVIE,
                    confidence=ConfidenceLevel.HIGH,
                    title="Old Movie",
                    year=2000,
                    tmdb_id=1,
                    metadata={"title": "Old Movie", "release_year": 2000, "tmdb_id": 1},
                ),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )
            self._mark_identified(manager, task, media_candidate, candidates)
            cd1_candidate = next(item for item in candidates if item.source_path.name.endswith("CD1.mkv"))

            updated = apply_source_candidate_tmdb_override(
                manager.get(task.id),
                media_candidate.id,
                tmdb_id=2,
                tmdb_client=_MovieTMDBOverride(),
            )
            updated_item = next(item for item in updated.plan_items if item.source_path == cd1_candidate.source_path)

            self.assertEqual(updated_item.evidence["movie_plan"]["part_token"], "CD1")
            self.assertEqual(
                updated_item.preview.proposed_relative_path,
                Path("Override Movie (2022) {tmdb-2}/Override Movie (2022) - CD1.mkv"),
            )

    def test_movie_source_candidate_override_updates_multipart_plan_items_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Avatar.2009"
            folder.mkdir()
            (folder / "Avatar.2009.CD1.mkv").write_text("disc 1", encoding="utf-8")
            (folder / "Avatar.2009.CD2.mkv").write_text("disc 2", encoding="utf-8")
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            candidates = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=MatchResult(
                    candidate_id=media_candidate.id,
                    media_type=MediaType.MOVIE,
                    confidence=ConfidenceLevel.HIGH,
                    title="Old Movie",
                    year=2000,
                    tmdb_id=1,
                    metadata={"title": "Old Movie", "release_year": 2000, "tmdb_id": 1},
                ),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )
            self._mark_identified(manager, task, media_candidate, candidates)

            updated = apply_source_candidate_tmdb_override(
                manager.get(task.id),
                media_candidate.id,
                tmdb_id=2,
                tmdb_client=_MovieTMDBOverride(),
            )

            self.assertEqual({candidate.manual_override_tmdb_id for candidate in updated.candidates}, {"2"})
            self.assertEqual({candidate.metadata["title"] for candidate in updated.candidates}, {"Override Movie"})
            self.assertTrue(
                any(
                    candidate.preview.proposed_relative_path
                    == Path("Override Movie (2022) {tmdb-2}/Override Movie (2022) - CD1.mkv")
                    for candidate in updated.candidates
                )
            )
            self.assertTrue(
                any(
                    candidate.preview.proposed_relative_path
                    == Path("Override Movie (2022) {tmdb-2}/Override Movie (2022) - CD2.mkv")
                    for candidate in updated.candidates
                )
            )

    def test_tv_source_candidate_override_preserves_episode_and_subtitle_plan_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            show = root / "The.Outcast.S02"
            show.mkdir()
            episode = show / "E01.mkv"
            episode.write_text("video", encoding="utf-8")
            subtitle = show / "E01.zh.srt"
            subtitle.write_text("subtitle", encoding="utf-8")
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._tv_origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            candidates = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=MatchResult(
                    candidate_id=media_candidate.id,
                    media_type=MediaType.TV,
                    confidence=ConfidenceLevel.HIGH,
                    title="Old Show",
                    year=2020,
                    tmdb_id=1,
                    metadata={"title": "Old Show", "release_year": 2020, "tmdb_id": 1},
                ),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )
            self._mark_identified(manager, task, media_candidate, candidates)

            updated = apply_source_candidate_tmdb_override(
                manager.get(task.id),
                media_candidate.id,
                tmdb_id=2,
                tmdb_client=_FakeTMDBOverride(),
            )

            self.assertEqual({candidate.manual_override_tmdb_id for candidate in updated.candidates}, {"2"})
            episode_candidate = next(candidate for candidate in updated.candidates if candidate.source_path == episode)
            subtitle_candidate = next(candidate for candidate in updated.candidates if candidate.source_path == subtitle)
            self.assertEqual(episode_candidate.evidence["tv_episode_plan"]["media_kind"], "video")
            self.assertEqual(subtitle_candidate.evidence["tv_episode_plan"]["media_kind"], "subtitle")
            self.assertEqual(
                episode_candidate.preview.proposed_relative_path,
                Path("Override Show (2021) {tmdb-2}/Season 2/Override Show - S02E01 - Override Pilot.mkv"),
            )
            self.assertEqual(
                subtitle_candidate.preview.proposed_relative_path,
                Path("Override Show (2021) {tmdb-2}/Season 2/Override Show - S02E01 - Override Pilot.srt"),
            )

    def test_source_candidate_override_rejects_unknown_candidate_and_wrong_media_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie = root / "Avatar.2009.mkv"
            movie.write_text("x", encoding="utf-8")
            media_candidate = scan_movie_root(root, TEST_MEDIA_EXTENSIONS)[0]
            manager = SessionBook()
            task = manager.create_for_origin(self._origin(root))
            manager.mark_scanned(task.id, [media_candidate])
            manager.start_identify(task.id)
            candidates = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=MatchResult(
                    candidate_id=media_candidate.id,
                    media_type=MediaType.MOVIE,
                    confidence=ConfidenceLevel.HIGH,
                    title="Old Movie",
                    year=2000,
                    tmdb_id=1,
                    metadata={"title": "Old Movie", "release_year": 2000, "tmdb_id": 1},
                ),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )
            self._mark_identified(manager, task, media_candidate, candidates)

            with self.assertRaises(Exception):
                apply_source_candidate_tmdb_override(
                    manager.get(task.id),
                    "missing",
                    tmdb_id=2,
                    tmdb_client=_MovieTMDBOverride(),
                )
            with self.assertRaises(Exception):
                apply_source_candidate_tmdb_override(
                    manager.get(task.id),
                    media_candidate.id,
                    tmdb_id=2,
                    tmdb_client=_WrongMediaTMDBOverride(),
                )

    def _origin(self, path: Path) -> Origin:
        return Origin(
            id="manual",
            name="Manual",
            path=path,
            media_type=MediaType.MOVIE,
            trigger=OriginTrigger.MANUAL,
            policy=OrganizePolicy(target_depot_id="Depot"),
        )

    def _tv_origin(self, path: Path) -> Origin:
        return Origin(
            id="tv-manual",
            name="TV Manual",
            path=path,
            media_type=MediaType.TV,
            trigger=OriginTrigger.MANUAL,
            policy=OrganizePolicy(target_depot_id="tv-Depot"),
        )

    def _depot(self, path: Path) -> Depot:
        return Depot(
            id="Depot",
            name="Movie Depot",
            path=path,
            media_type=MediaType.MOVIE,
            policy=TransferPolicy(target_library_path=path.parent / "library"),
        )

    def _tv_depot(self, path: Path) -> Depot:
        return Depot(
            id="tv-Depot",
            name="TV Depot",
            path=path,
            media_type=MediaType.TV,
            policy=TransferPolicy(target_library_path=path.parent / "library"),
        )

    def _source_edit(
        self,
        manager: SessionBook,
        session_id: str,
        source_candidate_id: str,
        *,
        target_depot: Depot | None = None,
    ) -> SourceEdit:
        return SourceEdit(
            manager.get(session_id),
            source_candidate_id,
            extensions=TEST_MEDIA_EXTENSIONS,
            target_depot=target_depot,
        )

    def _candidate(
        self,
        candidate_id: str,
        confidence: ConfidenceLevel,
        *,
        source_path: Path | None = None,
        metadata: dict | None = None,
        source: str | None = "auto",
    ) -> OrganizePlanItem:
        return OrganizePlanItem(
            id=candidate_id,
            source_path=source_path or Path("C:/source.mkv"),
            confidence=confidence,
            metadata=metadata or {"title": "Movie", "year": 2020, "tmdb_id": 1},
            metadata_source=source,
            preview=CandidatePreview(proposed_relative_path=Path("Movie/Movie.mkv")),
        )

    def _mark_identified(
        self,
        manager: SessionBook,
        task,
        media_candidate,
        plan_items,
    ) -> None:
        first = plan_items[0] if plan_items else None
        manager.mark_identified(
            task.id,
            candidate_matches={
                media_candidate.id: CandidateMatch(
                    source_candidate_id=media_candidate.id,
                    confidence=first.confidence if first else ConfidenceLevel.NONE,
                    metadata=dict(first.metadata or {}) if first else None,
                    metadata_source=first.metadata_source if first else None,
                )
            },
            plan_items=list(plan_items),
        )

    def _store(self, root: Path) -> Store:
        store = Store(root / "state.sqlite")
        store.initialize()
        return store

    def _organizer(
        self,
        store: Store,
        *,
        min_non_subtitle_file_size_bytes: int | None = None,
    ) -> OrganizeExecutor:
        return OrganizeExecutor(
            locks=DepotLockRegistry(),
            activity=ActivityRecorder(store),
            sidecar_extensions=TEST_MEDIA_EXTENSIONS.sidecar,
            subtitle_extensions=TEST_MEDIA_EXTENSIONS.subtitle,
            extensions=TEST_MEDIA_EXTENSIONS,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )

class _FakeTMDBOverride:
    def get_by_id(self, media_type, tmdb_id):
        return TMDBCandidate(
            tmdb_id,
            media_type,
            "Override Show",
            year=2021,
            metadata={
                "title": "Override Show",
                "release_year": 2021,
                "tmdb_id": tmdb_id,
                "episode_titles": {2: {1: "Override Pilot"}},
            },
        )


class _FallbackTMDBOverride:
    def get_by_id(self, media_type, tmdb_id):
        return TMDBCandidate(
            tmdb_id,
            media_type,
            "Override Show",
            year=2021,
            metadata={
                "title": "Override Show",
                "release_year": 2021,
                "tmdb_id": tmdb_id,
                "episode_titles": {2: {7: "Override Corrected"}},
            },
        )


class _CatalogOnlyTMDBOverride:
    def get_by_id(self, media_type, tmdb_id):
        return TMDBCandidate(
            tmdb_id,
            media_type,
            "Override Show",
            year=2021,
            metadata={
                "title": "Override Show",
                "release_year": 2021,
                "tmdb_id": tmdb_id,
            },
        )


class _MovieTMDBOverride:
    def get_by_id(self, media_type, tmdb_id):
        return TMDBCandidate(
            tmdb_id,
            media_type,
            "Override Movie",
            year=2022,
            metadata={
                "title": "Override Movie",
                "release_year": 2022,
                "tmdb_id": tmdb_id,
            },
        )


class _WrongMediaTMDBOverride:
    def get_by_id(self, media_type, tmdb_id):
        wrong_type = MediaType.TV if media_type == MediaType.MOVIE else MediaType.MOVIE
        return TMDBCandidate(
            tmdb_id,
            wrong_type,
            "Wrong Media",
            year=2022,
            metadata={"title": "Wrong Media", "release_year": 2022, "tmdb_id": tmdb_id},
        )


class _FallbackTVMatcher:
    def __init__(self):
        self.extractor = FakeTVEpisodeExtractor(
            {"UglyNameA.mkv": {"season": 2, "episode": 7, "end_episode": None}}
        )
        self.tv_episode_planner = TVEpisodePlanner(
            extensions=TEST_MEDIA_EXTENSIONS,
            episode_extractor=self.extractor,
            episode_catalog_provider=FakeTVEpisodeCatalogProvider(TVEpisodeCatalog({2: {7: "Corrected"}})),
        )

    def match_batch(self, candidates):
        return {
            candidate.id: MatchResult(
                candidate_id=candidate.id,
                media_type=MediaType.TV,
                confidence=ConfidenceLevel.HIGH,
                title="Example Show",
                year=2020,
                tmdb_id=1,
                metadata={"title": "Example Show", "release_year": 2020, "tmdb_id": 1},
            )
            for candidate in candidates
        }


if __name__ == "__main__":
    unittest.main()
