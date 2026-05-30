from __future__ import annotations

from datetime import datetime
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.core.error import ConfigurationError
from app.infra.db.store import Store
from app.domain.activity import ActivityStatus
from app.domain.media import MediaType
from app.domain.transfer import TransferErrorCode, TransferStatus, TransferTrigger
from app.domain.depot import Depot as DepotConfig, TransferPolicy
from app.domain.rule import RuleCondition, RuleOperator, RuleCategory, TransferRule
from app.domain.transfer import TransferJob
from app.services.depot.service import DepotService
from app.services.transfer.schedule import TransferService, TransferScheduler, validate_cron_schedule
from app.services.depot.candidate import CandidateBook, CandidateScope
from app.services.depot.lock import DepotLockRegistry
from app.services.activity.recorder import ActivityRecorder
from app.engines.scan.depot import scan_depot_candidates
from app.infra.fs.result import MoveResult, StorageMoveStatus
from app.services.transfer.worker import TransferRejected, TransferWorker
from support import TEST_MEDIA_EXTENSIONS


class TransferWorkflowTests(unittest.TestCase):
    def test_depot_detail_sorts_ungrouped_first_then_group_like_by_pinyin(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            self._movie_file(Depot, "测试10 (2020) {tmdb-10}", "Movie.mkv", "x")
            self._movie_file(Depot, "测试2 (2020) {tmdb-2}", "Movie.mkv", "x")
            self._movie_file(Depot, "阿凡达 (2009) {tmdb-19995}", "Movie.mkv", "x")
            self._movie_file(Depot, "组B/苹果 (2020) {tmdb-4}", "Movie.mkv", "x")
            self._movie_file(Depot, "组A/香蕉 (2020) {tmdb-3}", "Movie.mkv", "x")
            (Depot.path / "组A2").mkdir(parents=True)

            detail = DepotService(
                locks=ctx.locks,
                activity=ActivityRecorder(ctx.store),
                extensions=TEST_MEDIA_EXTENSIONS,
            ).depot_detail(Depot)

            self.assertEqual(
                [(candidate.display_name, candidate.group.display_name if candidate.group else None) for candidate in detail.candidates],
                [
                    ("阿凡达 (2009) {tmdb-19995}", None),
                    ("测试2 (2020) {tmdb-2}", None),
                    ("测试10 (2020) {tmdb-10}", None),
                    ("香蕉 (2020) {tmdb-3}", "组A"),
                    ("组A2", None),
                    ("苹果 (2020) {tmdb-4}", "组B"),
                ],
            )

    def test_transfer_rejects_duplicate_depot_but_allows_unrelated_queue(self) -> None:
        with self._store() as ctx:
            worker = self._worker(ctx.store, ctx.locks)
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)

            ctx.store.save_transfer_job(TransferJob(id="queued", depot_id=Depot.id, status=TransferStatus.QUEUED))
            with self.assertRaises(TransferRejected) as depot_busy:
                worker.create_job(Depot)
            self.assertEqual(depot_busy.exception.code, TransferErrorCode.DEPOT_TRANSFER_BUSY)

            other = ctx.Depot("other")
            ctx.store.save_depot(other)
            ctx.store.save_transfer_job(TransferJob(id="queued-other", depot_id=other.id, status=TransferStatus.QUEUED))
            ctx.store.save_transfer_job(TransferJob(id="queued", depot_id=Depot.id, status=TransferStatus.SUCCEEDED))
            job = worker.create_job(Depot)
            self.assertEqual(job.depot_id, Depot.id)

    def test_depot_lock_failure_fails_job(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)
            worker = self._worker(ctx.store, ctx.locks)
            job = worker.create_job(Depot)
            lease = ctx.locks.acquire(Depot, blocking=False)
            try:
                result = worker.execute(job, Depot)
            finally:
                lease.release()

            self.assertEqual(result.job.status, TransferStatus.FAILED)
            self.assertEqual(result.job.error_code, TransferErrorCode.DEPOT_LOCKED)
            self.assertEqual(len(result.activity_events), 1)

    def test_transfer_replaces_existing_target_and_applies_rule_fallback(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)
            source = Depot.path / "Avatar (2009) {tmdb-19995}" / "Avatar (2009).mkv"
            source.parent.mkdir(parents=True)
            source.write_text("new", encoding="utf-8")
            destination = Depot.policy.target_library_path / "Archive" / "2000" / source.relative_to(Depot.path)
            destination.parent.mkdir(parents=True)
            destination.write_text("old-content", encoding="utf-8")
            worker = self._worker(ctx.store, ctx.locks)
            job = worker.create_job(Depot)

            result = worker.execute(job, Depot, transfer_rule=TransferRule(id="rule", name="Archive Rule", fallback_bucket="Archive/{decade}"))

            self.assertEqual(result.job.status, TransferStatus.SUCCEEDED)
            self.assertEqual(destination.read_text(encoding="utf-8"), "new")
            context = _first_file_event(ctx.store).context
            self.assertEqual(context["overwritten_size"], len("old-content"))
            self.assertEqual(context["transfer_rule_id"], "rule")
            self.assertEqual(context["transfer_bucket"], "Archive/2000")
            self.assertEqual(context["depot_relative_path"], "Avatar (2009) {tmdb-19995}/Avatar (2009).mkv")
            self.assertEqual(context["destination_relative_path"], "Archive/2000/Avatar (2009) {tmdb-19995}/Avatar (2009).mkv")
            self.assertEqual(context["metadata_tmdb_id"], 19995)
            self.assertEqual(context["metadata_title"], "Avatar")
            self.assertEqual(context["metadata_year"], 2009)

    def test_transfer_skips_root_movie_file_without_package_folder(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)
            Depot.path.mkdir(parents=True)
            source = Depot.path / "Loose.mkv"
            source.write_text("loose", encoding="utf-8")
            library_marker = Depot.policy.target_library_path / "keep.txt"
            library_marker.parent.mkdir(parents=True)
            library_marker.write_text("keep", encoding="utf-8")
            worker = self._worker(ctx.store, ctx.locks)
            job = worker.create_job(Depot)

            result = worker.execute(job, Depot)

            self.assertEqual(result.job.status, TransferStatus.SKIPPED)
            self.assertEqual(result.skipped, 1)
            self.assertTrue(source.exists())
            self.assertTrue(library_marker.exists())
            event = _first_file_event(ctx.store)
            self.assertEqual(event.reason, "movie_transfer_requires_package_folder")
            self.assertEqual(event.context["blocked_reason"], "movie_transfer_requires_package_folder")

    def test_transfer_blocks_package_when_target_package_delete_fails(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)
            source = self._movie_file(Depot, "Avatar (2009) {tmdb-19995}", "Avatar (2009).mkv", "new")
            destination_root = Depot.policy.target_library_path / "Avatar (2009) {tmdb-19995}"
            destination_root.mkdir(parents=True)
            outside = ctx.root / "outside"
            outside.mkdir()
            try:
                (destination_root / "outside-link").symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlink unavailable: {exc}")
            worker = self._worker(ctx.store, ctx.locks)
            job = worker.create_job(Depot)

            result = worker.execute(job, Depot)

            self.assertEqual(result.job.status, TransferStatus.FAILED)
            self.assertEqual(result.failed, 1)
            self.assertTrue(source.exists())
            self.assertTrue(destination_root.exists())
            event = _first_file_event(ctx.store)
            self.assertEqual(event.status, ActivityStatus.FAILED)
            self.assertEqual(event.context["blocked_reason"], "contains_link_or_reparse_point")

    def test_transfer_places_organize_prefix_before_transfer_bucket(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)
            source = Depot.path / "欧美电影" / "科幻" / "Inception (2010) {tmdb-27205}" / "Inception.2010.2160p.mkv"
            source.parent.mkdir(parents=True)
            source.write_text("new", encoding="utf-8")
            destination = Depot.policy.target_library_path / "欧美电影" / "科幻" / "2010" / "Inception (2010) {tmdb-27205}" / "Inception.2010.2160p.mkv"
            worker = self._worker(ctx.store, ctx.locks)
            job = worker.create_job(Depot)

            result = worker.execute(job, Depot, transfer_rule=TransferRule(id="rule", name="Decade Rule", fallback_bucket="{decade}"))

            self.assertEqual(result.job.status, TransferStatus.SUCCEEDED)
            self.assertTrue(destination.exists())
            context = _first_file_event(ctx.store).context
            self.assertEqual(context["organize_prefix"], "欧美电影/科幻")
            self.assertIsNotNone(context["candidate_group_key"])
            self.assertEqual(context["transfer_bucket"], "2010")
            self.assertEqual(context["media_relative_path"], "Inception (2010) {tmdb-27205}/Inception.2010.2160p.mkv")
            self.assertEqual(context["destination_relative_path"], "欧美电影/科幻/2010/Inception (2010) {tmdb-27205}/Inception.2010.2160p.mkv")

    def test_transfer_rule_uses_package_path_without_splitting_movie_files(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)
            movie_root = Depot.path / "Movies" / "Avatar (2009) {tmdb-19995}"
            movie_root.mkdir(parents=True)
            (movie_root / "Avatar.2009.mkv").write_text("video", encoding="utf-8")
            (movie_root / "Avatar.2009.zh.srt").write_text("subtitle", encoding="utf-8")
            rule = TransferRule(
                id="rule",
                name="No File Rule",
                fallback_bucket="Archive",
                categories=[
                    RuleCategory(
                        name="extension",
                        bucket="Mkv",
                        conditions=[
                            RuleCondition(field="relative_path", op=RuleOperator.CONTAINS, value=".mkv"),
                        ],
                    )
                ],
            )
            worker = self._worker(ctx.store, ctx.locks)
            job = worker.create_job(Depot)

            result = worker.execute(job, Depot, transfer_rule=rule)

            self.assertEqual(result.job.status, TransferStatus.SUCCEEDED)
            destination_root = Depot.policy.target_library_path / "Movies" / "Archive" / "Avatar (2009) {tmdb-19995}"
            self.assertTrue((destination_root / "Avatar.2009.mkv").exists())
            self.assertTrue((destination_root / "Avatar.2009.zh.srt").exists())
            self.assertFalse((Depot.policy.target_library_path / "Movies" / "Mkv").exists())

    def test_transfer_rule_uses_show_root_without_matching_tv_season_folder(self) -> None:
        with self._store() as ctx:
            Depot = DepotConfig(
                id="tv",
                name="TV Depot",
                path=ctx.root / "tv",
                media_type=MediaType.TV,
                policy=TransferPolicy(target_library_path=ctx.root / "library" / "tv"),
            )
            ctx.store.save_depot(Depot)
            source = Depot.path / "TV" / "Example Show (2019) {tmdb-1}" / "Season 1" / "Example Show - S01E01.mkv"
            source.parent.mkdir(parents=True)
            source.write_text("video", encoding="utf-8")
            rule = TransferRule(
                id="rule",
                name="No Season Rule",
                fallback_bucket="{decade}",
                categories=[
                    RuleCategory(
                        name="season",
                        bucket="Season Bucket",
                        conditions=[
                            RuleCondition(field="relative_path", op=RuleOperator.CONTAINS, value="Season 1"),
                        ],
                    )
                ],
            )
            worker = self._worker(ctx.store, ctx.locks)
            job = worker.create_job(Depot)

            result = worker.execute(job, Depot, transfer_rule=rule)

            self.assertEqual(result.job.status, TransferStatus.SUCCEEDED)
            destination = (
                Depot.policy.target_library_path
                / "TV"
                / "2010"
                / "Example Show (2019) {tmdb-1}"
                / "Season 1"
                / "Example Show - S01E01.mkv"
            )
            self.assertTrue(destination.exists())
            self.assertFalse((Depot.policy.target_library_path / "TV" / "Season Bucket").exists())

    def test_transfer_skips_isolated_timeout_and_continues(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)
            first = self._movie_file(Depot, "A (2020) {tmdb-1}", "A.mkv", "a")
            second = self._movie_file(Depot, "B (2020) {tmdb-2}", "B.mkv", "b")
            worker = self._worker(ctx.store, ctx.locks)
            job = worker.create_job(Depot)

            def fake_move(source, destination, **_kwargs):
                if Path(source).name.lower() == "a.mkv":
                    return _timeout_result(Path(source), Path(destination))
                return _successful_move(Path(source), Path(destination))

            with mock.patch("app.services.transfer.worker.move_with_replace", side_effect=fake_move):
                result = worker.execute(job, Depot)

            self.assertEqual(result.job.status, TransferStatus.SUCCEEDED)
            self.assertEqual(result.moved, 1)
            self.assertEqual(result.skipped, 1)
            self.assertEqual(result.failed, 0)
            self.assertEqual(result.timed_out, 1)
            self.assertTrue(first.exists())
            self.assertTrue((Depot.policy.target_library_path / "B (2020) {tmdb-2}" / "B.mkv").exists())
            self.assertIn("timed_out=1", result.job.message)
            statuses = [event.status for event in result.activity_events if event.entity_type == "file"]
            self.assertCountEqual(statuses, [ActivityStatus.FAILED, ActivityStatus.SUCCEEDED])

    def test_transfer_success_resets_consecutive_timeout_count(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)
            self._movie_file(Depot, "A (2020) {tmdb-1}", "a.mkv", "a")
            self._movie_file(Depot, "B (2020) {tmdb-2}", "b.mkv", "b")
            self._movie_file(Depot, "C (2020) {tmdb-3}", "c.mkv", "c")
            worker = self._worker(ctx.store, ctx.locks)
            job = worker.create_job(Depot)

            def fake_move(source, destination, **_kwargs):
                if Path(source).name == "b.mkv":
                    return _successful_move(Path(source), Path(destination))
                return _timeout_result(Path(source), Path(destination))

            with mock.patch("app.services.transfer.worker.move_with_replace", side_effect=fake_move):
                result = worker.execute(job, Depot)

            self.assertEqual(result.job.status, TransferStatus.SUCCEEDED)
            self.assertEqual(result.moved, 1)
            self.assertEqual(result.skipped, 2)
            self.assertEqual(result.failed, 0)
            self.assertEqual(result.timed_out, 2)
            self.assertFalse(result.hard_timeout_stop)

    def test_transfer_consecutive_timeouts_fail_job_and_leave_depot_files(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)
            files = [
                self._movie_file(Depot, "A (2020) {tmdb-1}", "a.mkv", "a"),
                self._movie_file(Depot, "B (2020) {tmdb-2}", "b.mkv", "b"),
                self._movie_file(Depot, "C (2020) {tmdb-3}", "c.mkv", "c"),
            ]
            worker = self._worker(ctx.store, ctx.locks)
            job = worker.create_job(Depot)

            with mock.patch("app.services.transfer.worker.move_with_replace", side_effect=lambda source, destination, **_kwargs: _timeout_result(Path(source), Path(destination))):
                result = worker.execute(job, Depot)

            self.assertEqual(result.job.status, TransferStatus.FAILED)
            self.assertEqual(result.job.error_code, TransferErrorCode.MOVE_FAILED)
            self.assertEqual(result.failed, 1)
            self.assertEqual(result.timed_out, 2)
            self.assertTrue(result.hard_timeout_stop)
            for file in files:
                self.assertTrue(file.exists())

    def test_scheduler_uses_current_local_minute_without_replay(self) -> None:
        scheduler = TransferScheduler()
        Depot = DepotConfig(
            id="scheduled",
            name="Scheduled Depot",
            path=Path("C:/Depot"),
            media_type=MediaType.MOVIE,
            policy=TransferPolicy(
                target_library_path=Path("C:/library"),
                trigger=TransferTrigger.SCHEDULED,
                schedule="5 4 * * *",
            ),
        )
        now = datetime(2026, 5, 2, 4, 5).astimezone()

        self.assertEqual(scheduler.due_depots([Depot], now=now), [Depot])
        self.assertEqual(scheduler.due_depots([Depot], now=now), [])
        self.assertEqual(scheduler.due_depots([Depot], now=datetime(2026, 5, 2, 4, 6).astimezone()), [])

    def test_scheduler_retains_only_last_enqueued_minute_per_depot(self) -> None:
        scheduler = TransferScheduler()
        Depot = DepotConfig(
            id="scheduled",
            name="Scheduled Depot",
            path=Path("C:/Depot"),
            media_type=MediaType.MOVIE,
            policy=TransferPolicy(
                target_library_path=Path("C:/library"),
                trigger=TransferTrigger.SCHEDULED,
                schedule="* * * * *",
            ),
        )

        first_minute = datetime(2026, 5, 2, 4, 5).astimezone()
        next_minute = datetime(2026, 5, 2, 4, 6).astimezone()

        self.assertEqual(scheduler.due_depots([Depot], now=first_minute), [Depot])
        self.assertEqual(scheduler.due_depots([Depot], now=next_minute), [Depot])

        self.assertEqual(len(scheduler._last_enqueued_minute_by_depot), 1)
        self.assertEqual(scheduler._last_enqueued_minute_by_depot[Depot.id], next_minute.strftime("%Y-%m-%dT%H:%M%z"))

    def test_cron_schedule_validation_accepts_supported_fields(self) -> None:
        for schedule in [
            "5 4 * * *",
            "*/15 0,12 1-15 1,6 0-6",
        ]:
            with self.subTest(schedule=schedule):
                validate_cron_schedule(schedule)

    def test_cron_schedule_validation_rejects_invalid_fields(self) -> None:
        for schedule in [
            "* * * *",
            "x * * * *",
            "*/0 * * * *",
            "-1 * * * *",
            "60 * * * *",
            "* 24 * * *",
            "* * 0 * *",
            "* * * 13 *",
            "* * * * 7",
            "10-5 * * * *",
            "1-10/2 * * * *",
        ]:
            with self.subTest(schedule=schedule):
                with self.assertRaises(ConfigurationError):
                    validate_cron_schedule(schedule)

    def test_scheduler_skips_invalid_legacy_schedule_without_crashing(self) -> None:
        scheduler = TransferScheduler()
        Depot = DepotConfig(
            id="scheduled",
            name="Scheduled Depot",
            path=Path("C:/Depot"),
            media_type=MediaType.MOVIE,
            policy=TransferPolicy(
                target_library_path=Path("C:/library"),
                trigger=TransferTrigger.SCHEDULED,
                schedule="*/0 * * * *",
            ),
        )

        self.assertEqual(scheduler.due_depots([Depot], now=datetime(2026, 5, 2, 4, 5).astimezone()), [])

    def test_transfer_automation_enqueues_due_scheduled_depot(self) -> None:
        with self._store() as ctx:
            Depot = DepotConfig(
                id="scheduled",
                name="Scheduled Depot",
                path=ctx.root / "scheduled",
                media_type=MediaType.MOVIE,
                policy=TransferPolicy(
                    target_library_path=ctx.root / "library" / "scheduled",
                    trigger=TransferTrigger.SCHEDULED,
                    schedule="5 4 * * *",
                ),
            )
            self._movie_file(Depot, "Ready (2020) {tmdb-1}", "Ready.mkv", "ready")
            ctx.store.save_depot(Depot)
            worker = self._worker(ctx.store, ctx.locks)
            automation = TransferService(
                configuration=FakeConfiguration([Depot]),
                worker=worker,
                poll_interval_seconds=999,
            )

            results = automation.poll_once(now=datetime(2026, 5, 2, 4, 5).astimezone())

            self.assertEqual(results, [])
            queued = ctx.store.list_transfer_jobs(statuses=[TransferStatus.QUEUED])
            self.assertEqual(len(queued), 1)
            self.assertEqual(queued[0].depot_id, "scheduled")
            result = automation.run_queued_once()
            self.assertIsNotNone(result)
            self.assertEqual(result.job.status, TransferStatus.SUCCEEDED)
            self.assertTrue((Depot.policy.target_library_path / "Ready (2020) {tmdb-1}" / "Ready.mkv").exists())

    def test_transfer_queue_can_sequence_one_depot_at_a_time(self) -> None:
        with self._store() as ctx:
            first = ctx.Depot("first")
            second = ctx.Depot("second")
            ctx.store.save_depot(first)
            ctx.store.save_depot(second)
            for depot in [first, second]:
                self._movie_file(depot, f"{depot.id.title()} (2020) {{tmdb-1}}", f"{depot.id}.mkv", depot.id)
            worker = self._worker(ctx.store, ctx.locks)

            for depot in [first, second]:
                job = worker.create_job(depot, requested_by="queue")
                result = worker.execute(job, depot)
                self.assertEqual(result.job.status, TransferStatus.SUCCEEDED)

            self.assertTrue((first.policy.target_library_path / "First (2020) {tmdb-1}" / "first.mkv").exists())
            self.assertTrue((second.policy.target_library_path / "Second (2020) {tmdb-1}" / "second.mkv").exists())

    def test_queued_jobs_run_in_created_order_without_batches(self) -> None:
        with self._store() as ctx:
            first = ctx.Depot("first")
            second = ctx.Depot("second")
            ctx.store.save_depot(first)
            ctx.store.save_depot(second)
            for depot in [first, second]:
                self._movie_file(depot, f"{depot.id.title()} (2020) {{tmdb-1}}", f"{depot.id}.mkv", depot.id)
            chain = TransferService(configuration=FakeConfiguration([first, second]), worker=self._worker(ctx.store, ctx.locks))
            chain.enqueue(first, requested_by="test")
            chain.enqueue(second, requested_by="test")

            first_result = chain.run_queued_once()
            second_result = chain.run_queued_once()

            self.assertEqual(first_result.job.depot_id, "first")
            self.assertEqual(second_result.job.depot_id, "second")
            self.assertTrue((first.policy.target_library_path / "First (2020) {tmdb-1}" / "first.mkv").exists())
            self.assertTrue((second.policy.target_library_path / "Second (2020) {tmdb-1}" / "second.mkv").exists())

    def test_cancel_queued_job_marks_it_cancelled_and_skips_worker(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)
            chain = TransferService(configuration=FakeConfiguration([Depot]), worker=self._worker(ctx.store, ctx.locks))
            job = chain.enqueue(Depot, requested_by="test")

            cancelled = chain.cancel_job(job.id)

            self.assertEqual(cancelled.status, TransferStatus.CANCELLED)
            self.assertIsNone(chain.run_queued_once())
            self.assertEqual(ctx.store.get_transfer_job(job.id).status, TransferStatus.CANCELLED)

    def test_running_job_cancels_cooperatively_between_files(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)
            first = self._movie_file(Depot, "A (2020) {tmdb-1}", "a.mkv", "a")
            second = self._movie_file(Depot, "B (2020) {tmdb-2}", "b.mkv", "b")
            worker = self._worker(ctx.store, ctx.locks)
            job = worker.create_job(Depot)

            def fake_move(source, destination, **_kwargs):
                result = _successful_move(Path(source), Path(destination))
                stored = ctx.store.get_transfer_job(job.id)
                stored.status = TransferStatus.CANCELLING
                ctx.store.save_transfer_job(stored)
                return result

            with mock.patch("app.services.transfer.worker.move_with_replace", side_effect=fake_move):
                result = worker.execute(job, Depot)

            self.assertEqual(result.job.status, TransferStatus.CANCELLED)
            self.assertTrue((Depot.policy.target_library_path / "A (2020) {tmdb-1}" / "a.mkv").exists())
            self.assertTrue(second.exists())
            self.assertEqual(result.activity_events[-1].summary, "Transfer cancelled after 1 file transferred")

    def test_startup_recovery_marks_stale_running_and_cancelling_jobs_failed(self) -> None:
        with self._store() as ctx:
            first = ctx.Depot("first")
            second = ctx.Depot("second")
            ctx.store.save_depot(first)
            ctx.store.save_depot(second)
            chain = TransferService(configuration=FakeConfiguration([first, second]), worker=self._worker(ctx.store, ctx.locks))
            ctx.store.save_transfer_job(TransferJob(id="running", depot_id="first", status=TransferStatus.RUNNING))
            ctx.store.save_transfer_job(TransferJob(id="cancelling", depot_id="second", status=TransferStatus.CANCELLING))

            recovered = chain.recover_stale_running_jobs()

            self.assertEqual({job.id for job in recovered}, {"running", "cancelling"})
            self.assertEqual(ctx.store.get_transfer_job("running").status, TransferStatus.FAILED)
            self.assertEqual(ctx.store.get_transfer_job("running").error_code, TransferErrorCode.INTERRUPTED)
            self.assertEqual(ctx.store.get_transfer_job("cancelling").status, TransferStatus.FAILED)
            self.assertEqual(ctx.store.get_transfer_job("cancelling").error_code, TransferErrorCode.INTERRUPTED)

    def test_transfer_all_moves_candidate_sidecars_and_nested_regular_files(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)
            folder = Depot.path / "Movie"
            nested = folder / "extras"
            nested.mkdir(parents=True)
            (folder / "Movie.mkv").write_text("video", encoding="utf-8")
            (folder / "Movie.nfo").write_text("metadata", encoding="utf-8")
            (folder / "sample.mkv").write_text("x", encoding="utf-8")
            (nested / "debug.bin").write_text("debug", encoding="utf-8")
            (nested / "poster.jpg").write_text("poster", encoding="utf-8")
            worker = self._worker(ctx.store, ctx.locks)
            job = worker.create_job(Depot)

            result = worker.execute(job, Depot)

            self.assertEqual(result.job.status, TransferStatus.SUCCEEDED)
            self.assertTrue((Depot.policy.target_library_path / "Movie" / "Movie.mkv").exists())
            self.assertTrue((Depot.policy.target_library_path / "Movie" / "Movie.nfo").exists())
            self.assertTrue((Depot.policy.target_library_path / "Movie" / "sample.mkv").exists())
            self.assertTrue((Depot.policy.target_library_path / "Movie" / "extras" / "debug.bin").exists())
            self.assertTrue((Depot.policy.target_library_path / "Movie" / "extras" / "poster.jpg").exists())
            self.assertFalse(folder.exists())

    def test_transfer_selected_file_and_folder_candidates(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)
            folder = Depot.path / "Movie"
            folder.mkdir(parents=True)
            (folder / "Movie.mkv").write_text("video", encoding="utf-8")
            (folder / "Movie.nfo").write_text("metadata", encoding="utf-8")
            (Depot.path / "Loose.mkv").write_text("loose", encoding="utf-8")
            candidates = {candidate.display_name: candidate for candidate in scan_depot_candidates(Depot, TEST_MEDIA_EXTENSIONS)}
            worker = self._worker(ctx.store, ctx.locks)
            job = worker.create_job(Depot, candidate_ids=[candidates["Movie"].id])

            result = worker.execute(job, Depot)

            self.assertEqual(result.job.status, TransferStatus.SUCCEEDED)
            self.assertTrue((Depot.policy.target_library_path / "Movie" / "Movie.mkv").exists())
            self.assertTrue((Depot.policy.target_library_path / "Movie" / "Movie.nfo").exists())
            self.assertFalse((Depot.policy.target_library_path / "Loose.mkv").exists())
            self.assertTrue((Depot.path / "Loose.mkv").exists())
            self.assertEqual(result.job.metadata["candidate_scope"][0]["relative_path"], "Movie")

    def test_depot_candidate_scope_payload_round_trips_through_owner(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            folder = Depot.path / "Movie"
            folder.mkdir(parents=True)
            (folder / "Movie.mkv").write_text("video", encoding="utf-8")
            candidate = scan_depot_candidates(Depot, TEST_MEDIA_EXTENSIONS)[0]
            book = CandidateBook(Depot, TEST_MEDIA_EXTENSIONS)

            payload = book.scope(candidate).as_dict()
            restored = CandidateScope.from_payload(payload)

            self.assertIsNotNone(restored)
            self.assertEqual(restored.relative_path, Path("Movie"))
            self.assertEqual(restored.relative_path_text, "Movie")
            self.assertEqual(book.from_scope(restored).id, candidate.id)

    def test_transfer_selected_candidate_missing_at_execution_is_recorded(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)
            folder = Depot.path / "Movie"
            folder.mkdir(parents=True)
            (folder / "Movie.mkv").write_text("video", encoding="utf-8")
            candidate = scan_depot_candidates(Depot, TEST_MEDIA_EXTENSIONS)[0]
            worker = self._worker(ctx.store, ctx.locks)
            job = worker.create_job(Depot, candidate_ids=[candidate.id])
            for path in folder.iterdir():
                path.unlink()
            folder.rmdir()

            result = worker.execute(job, Depot)

            self.assertEqual(result.job.status, TransferStatus.SKIPPED)
            self.assertEqual(result.skipped, 1)
            self.assertEqual(result.activity_events[0].summary, "Selected Depot candidate is missing")

    def test_transfer_rejects_unknown_selected_candidate_without_enqueueing(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            ctx.store.save_depot(Depot)
            worker = self._worker(ctx.store, ctx.locks)

            with self.assertRaises(ConfigurationError):
                worker.create_job(Depot, candidate_ids=["missing"])

            self.assertEqual(ctx.store.list_transfer_jobs(), [])

    def test_return_moves_selected_files_and_records_activity(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            source = Depot.path / "Movie" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_text("x", encoding="utf-8")
            destination_root = ctx.root / "return"

            activity_events = DepotService(locks=ctx.locks, activity=ActivityRecorder(ctx.store)).return_items(
                Depot,
                [Path("Movie/Movie.mkv")],
                destination_root,
            )

            self.assertEqual(len(activity_events), 1)
            self.assertTrue((destination_root / "Movie" / "Movie.mkv").exists())

    def test_return_file_scope_leaves_unselected_sidecars_in_depot(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            source_folder = Depot.path / "Movie"
            source = source_folder / "Movie.mkv"
            source_folder.mkdir(parents=True)
            source.write_text("x", encoding="utf-8")
            (source_folder / "movie.nfo").write_text("metadata", encoding="utf-8")
            destination_root = ctx.root / "return"

            activity_events = DepotService(
                locks=ctx.locks,
                activity=ActivityRecorder(ctx.store),
                sidecar_extensions=TEST_MEDIA_EXTENSIONS.sidecar,
            ).return_items(Depot, [Path("Movie/Movie.mkv")], destination_root)

            self.assertEqual(len(activity_events), 1)
            self.assertTrue((destination_root / "Movie" / "Movie.mkv").exists())
            self.assertTrue(source_folder.exists())
            self.assertTrue((source_folder / "movie.nfo").exists())
            self.assertEqual(activity_events[0].context["cleanup_stopped_at"], "Movie")
            self.assertEqual(activity_events[0].context["cleanup_stop_reason"], "contains_non_sidecar")

    def test_return_moves_selected_depot_candidate_tree(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            source_folder = Depot.path / "Movie"
            source_folder.mkdir(parents=True)
            (source_folder / "Movie.mkv").write_text("video", encoding="utf-8")
            (source_folder / "Movie.nfo").write_text("metadata", encoding="utf-8")
            destination_root = ctx.root / "return"
            candidate = scan_depot_candidates(Depot, TEST_MEDIA_EXTENSIONS)[0]

            activity_events = DepotService(
                locks=ctx.locks,
                activity=ActivityRecorder(ctx.store),
                store=ctx.store,
                extensions=TEST_MEDIA_EXTENSIONS,
                sidecar_extensions=TEST_MEDIA_EXTENSIONS.sidecar,
            ).return_items(Depot, [], destination_root, candidate_ids=[candidate.id])

            self.assertEqual(len(activity_events), 1)
            self.assertTrue((destination_root / "Movie" / "Movie.mkv").exists())
            self.assertTrue((destination_root / "Movie" / "Movie.nfo").exists())
            self.assertFalse(source_folder.exists())

    def test_return_skips_blocked_depot_candidate_tree(self) -> None:
        with self._store() as ctx:
            Depot = ctx.Depot("Depot")
            outside = ctx.root / "outside"
            outside.mkdir()
            source_folder = Depot.path / "Movie"
            source_folder.mkdir(parents=True)
            (source_folder / "Movie.mkv").write_text("video", encoding="utf-8")
            try:
                (source_folder / "outside-link").symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlink unavailable: {exc}")
            destination_root = ctx.root / "return"
            candidate = scan_depot_candidates(Depot, TEST_MEDIA_EXTENSIONS)[0]

            activity_events = DepotService(
                locks=ctx.locks,
                activity=ActivityRecorder(ctx.store),
                store=ctx.store,
                extensions=TEST_MEDIA_EXTENSIONS,
                sidecar_extensions=TEST_MEDIA_EXTENSIONS.sidecar,
            ).return_items(Depot, [], destination_root, candidate_ids=[candidate.id])

            self.assertEqual(len(activity_events), 1)
            self.assertEqual(activity_events[0].status, ActivityStatus.SKIPPED)
            self.assertEqual(activity_events[0].context["blocked_reason"], "contains_link_or_reparse_point")
            self.assertTrue(source_folder.exists())
            self.assertFalse((destination_root / "Movie").exists())

    def _worker(self, store: Store, locks: DepotLockRegistry) -> TransferWorker:
        return TransferWorker(
            store=store,
            locks=locks,
            activity=ActivityRecorder(store),
            extensions=TEST_MEDIA_EXTENSIONS,
        )

    def _movie_file(self, Depot: DepotConfig, folder: str, filename: str, content: str) -> Path:
        path = Depot.path / folder / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _store(self):
        class Context:
            def __enter__(inner):
                inner.temp = tempfile.TemporaryDirectory()
                inner.root = Path(inner.temp.name)
                inner.store = Store(inner.root / "state.sqlite")
                inner.store.initialize()
                inner.locks = DepotLockRegistry()
                return inner

            def __exit__(inner, exc_type, exc, tb):
                inner.store.close()
                inner.temp.cleanup()

            def Depot(inner, depot_id: str) -> DepotConfig:
                return DepotConfig(
                    id=depot_id,
                    name=f"{depot_id} Depot",
                    path=inner.root / depot_id,
                    media_type=MediaType.MOVIE,
                    policy=TransferPolicy(target_library_path=inner.root / "library" / depot_id),
                )

        return Context()


def _first_file_event(store: Store):
    return next(event for event in store.list_activity_events() if event.entity_type == "file")


def _timeout_result(source: Path, destination: Path) -> MoveResult:
    return MoveResult(
        status=StorageMoveStatus.TIMEOUT,
        source_path=source,
        destination_path=destination,
        message="Move timed out; source remains available for retry",
        error_type="MoveTimeout",
        timed_out=True,
        source_exists_after=True,
        destination_exists_after=False,
    )


def _successful_move(source: Path, destination: Path) -> MoveResult:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    return MoveResult(
        status=StorageMoveStatus.SUCCEEDED,
        source_path=source,
        destination_path=destination,
        message="Moved",
        source_exists_after=False,
        destination_exists_after=True,
    )


class FakeConfiguration:
    def __init__(self, depots):
        self.depots = depots

    def list_depots(self):
        return self.depots


if __name__ == "__main__":
    unittest.main()
