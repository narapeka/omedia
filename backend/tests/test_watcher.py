from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.config.location import LocationService, StrictPathValidator
from app.services.watch.organize import WatchOrganizeRun
from app.services.watch.service import WatchService
from app.core.error import ConfigurationError
from app.infra.db.store import Store
from app.domain.match import ConfidenceLevel
from app.domain.media import MediaType
from app.domain.origin import OriginTrigger
from app.domain.transfer import TransferTrigger
from app.domain.origin import OrganizePolicy, Origin
from app.domain.depot import Depot, TransferPolicy
from app.domain.watch import WatchSettings
from app.domain.match import MatchResult
from app.domain.tv import TVEpisodeCatalog
from app.services.depot.lock import DepotLockRegistry
from app.services.activity.recorder import ActivityRecorder
from app.services.watch.buffer import WatchEventBuffer
from app.services.organize.execute import OrganizeExecutor
from app.engines.plan.tv.planner import TVEpisodePlanner
from support import FakeTVEpisodeCatalogProvider, FakeTVEpisodeExtractor, TEST_MEDIA_EXTENSIONS


class WatcherTests(unittest.TestCase):
    def test_watch_settings_validation_requires_direct_child_watch_origin(self) -> None:
        validator = StrictPathValidator()
        config = WatchSettings(path=Path("C:/watch"))
        bad = Origin(
            id="bad",
            name="Bad Origin",
            path=Path("C:/watch/nested/bad"),
            media_type=MediaType.MOVIE,
            trigger=OriginTrigger.WATCH,
            policy=OrganizePolicy(target_depot_id="Depot"),
        )

        with self.assertRaises(ConfigurationError):
            validator.validate_origin(bad, watch_settings=config, origins=[], depots=[])

    def test_manual_origin_overlap_with_watch_settings_is_rejected_in_both_directions(self) -> None:
        validator = StrictPathValidator()
        config = WatchSettings(path=Path("C:/watch"))
        manual = Origin(
            id="manual",
            name="Manual Origin",
            path=Path("C:/watch/manual"),
            media_type=MediaType.MOVIE,
            trigger=OriginTrigger.MANUAL,
            policy=OrganizePolicy(target_depot_id="Depot"),
        )

        with self.assertRaises(ConfigurationError):
            validator.validate_origin(manual, watch_settings=config, origins=[], depots=[])
        with self.assertRaises(ConfigurationError):
            validator.validate_watch_settings(config, origins=[manual], depots=[])

    def test_watch_root_replacement_clears_watch_origins_and_keeps_manual_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = Store(root / "state.sqlite")
            store.initialize()
            try:
                configuration = LocationService(store)
                depot = self._depot(root / "Depot")
                old_root = root / "watch"
                new_root = root / "new-watch"
                manual_path = root / "manual"
                configuration.save_depot(depot)
                configuration.save_watch_settings(WatchSettings(path=old_root, enabled=True))
                configuration.save_origin(self._watch_origin(old_root / "auto", depot.path))
                configuration.save_origin(
                    Origin(
                        id="manual",
                        name="Manual",
                        path=manual_path,
                        media_type=MediaType.MOVIE,
                        trigger=OriginTrigger.MANUAL,
                        policy=OrganizePolicy(target_depot_id=depot.id),
                    )
                )

                with self.assertRaises(ConfigurationError):
                    configuration.save_watch_settings(WatchSettings(path=manual_path / "nested", enabled=True))
                self.assertEqual({origin.id for origin in configuration.list_origins()}, {"auto", "manual"})

                saved = configuration.save_watch_settings(WatchSettings(path=new_root, enabled=True))

                self.assertFalse(saved.enabled)
                self.assertEqual(configuration.get_watch_settings().path, new_root)
                origins = configuration.list_origins()
                self.assertEqual([origin.id for origin in origins], ["manual"])
            finally:
                store.close()

    def test_scheduled_depot_requires_schedule(self) -> None:
        validator = StrictPathValidator()
        depot = Depot(
            id="scheduled",
            name="Scheduled Depot",
            path=Path("C:/Depot/scheduled"),
            media_type=MediaType.MOVIE,
            policy=TransferPolicy(
                target_library_path=Path("C:/library/scheduled"),
                trigger=TransferTrigger.SCHEDULED,
                schedule=None,
            ),
        )

        with self.assertRaises(ConfigurationError):
            validator.validate_depot(depot, watch_settings=None, origins=[], depots=[])

    def test_scheduled_depot_rejects_invalid_schedule(self) -> None:
        validator = StrictPathValidator()
        depot = Depot(
            id="scheduled",
            name="Scheduled Depot",
            path=Path("C:/Depot/scheduled"),
            media_type=MediaType.MOVIE,
            policy=TransferPolicy(
                target_library_path=Path("C:/library/scheduled"),
                trigger=TransferTrigger.SCHEDULED,
                schedule="*/0 * * * *",
            ),
        )

        with self.assertRaises(ConfigurationError):
            validator.validate_depot(depot, watch_settings=None, origins=[], depots=[])

    def test_watch_settings_filters_and_debounces_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "watch"
            origin_path = root / "auto"
            unknown_path = origin_path / ".unknown"
            origin_path.mkdir(parents=True)
            unknown_path.mkdir()
            worker = self._watch_worker(root, origin_path)
            (origin_path / "file.mkv").write_text("x", encoding="utf-8")
            (unknown_path / "file.mkv").write_text("x", encoding="utf-8")

            self.assertIsNotNone(worker.handle_event(origin_path / "file.mkv", now=100))
            self.assertIsNone(worker.handle_event(root / "other" / "file.mkv", now=100))
            self.assertIsNone(worker.handle_event(unknown_path / "file.mkv", now=100))
            self.assertEqual(worker.flush_ready(now=100.5), [])
            self.assertEqual(len(worker.flush_ready(now=102)), 1)

    def test_watch_settings_backlog_excludes_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "watch"
            origin_path = root / "auto"
            unknown_path = origin_path / ".unknown"
            unknown_path.mkdir(parents=True)
            (origin_path / "Avatar.mkv").write_text("x", encoding="utf-8")
            (unknown_path / "Bad.mkv").write_text("x", encoding="utf-8")

            backlog = self._watch_worker(root, origin_path).start()

            self.assertEqual([item.path.name for item in backlog], ["Avatar.mkv"])

    def test_watch_organize_matched_and_unmatched_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            watch = root / "watch"
            origin_path = watch / "auto"
            depot_path = root / "Depot"
            origin_path.mkdir(parents=True)
            (origin_path / "Avatar.mkv").write_text("movie", encoding="utf-8")
            store = Store(root / "state.sqlite")
            store.initialize()
            try:
                Depot = self._depot(depot_path)
                chain = self._watch_chain(store, Depot, ConfidenceLevel.HIGH)
                result = chain.process_origin(self._watch_origin(origin_path, depot_path))

                self.assertEqual(result.matched, 1)
                self.assertTrue((depot_path / "Avatar (2009) {tmdb-19995}" / "Avatar (2009).mkv").exists())
                context = store.list_activity_events()[0].context
                self.assertEqual(context["origin_id"], "auto")
                self.assertEqual(context["source_relative_path"], "Avatar.mkv")
                self.assertEqual(context["depot_relative_path"], "Avatar (2009) {tmdb-19995}/Avatar (2009).mkv")
                self.assertEqual(context["metadata_tmdb_id"], 19995)
            finally:
                store.close()

            origin_path.mkdir(parents=True, exist_ok=True)
            (origin_path / "Unknown.mkv").write_text("movie", encoding="utf-8")
            store = Store(root / "state2.sqlite")
            store.initialize()
            try:
                chain = self._watch_chain(store, Depot, ConfidenceLevel.NONE)
                result = chain.process_origin(self._watch_origin(origin_path, depot_path))

                self.assertEqual(result.unmatched, 1)
                self.assertTrue((origin_path / ".unknown" / "Unknown.mkv").exists())
                context = store.list_activity_events()[0].context
                self.assertEqual(context["origin_id"], "auto")
                self.assertEqual(context["source_relative_path"], "Unknown.mkv")
                self.assertEqual(context["destination_relative_path"], ".unknown/Unknown.mkv")
                self.assertEqual(context["move_status"], "succeeded")
            finally:
                store.close()

    def test_watch_organize_movie_folder_moves_selected_subtitles_and_excludes_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            origin_path = root / "watch" / "auto"
            depot_path = root / "Depot"
            folder = origin_path / "Avatar.2009"
            folder.mkdir(parents=True)
            for name in [
                "Avatar.2009.mkv",
                "Avatar.2009.srt",
                "Avatar.2009.zh.srt",
                "Avatar.2009.sup",
                "movie.nfo",
            ]:
                (folder / name).write_text("x", encoding="utf-8")
            store = Store(root / "state.sqlite")
            store.initialize()
            try:
                Depot = self._depot(depot_path)
                chain = self._watch_chain(store, Depot, ConfidenceLevel.HIGH)
                result = chain.process_origin(self._watch_origin(origin_path, depot_path))

                self.assertEqual(result.matched, 3)
                destination = depot_path / "Avatar (2009) {tmdb-19995}"
                self.assertTrue((destination / "Avatar (2009).mkv").exists())
                self.assertTrue((destination / "Avatar (2009).srt").exists())
                self.assertTrue((destination / "Avatar (2009).sup").exists())
                self.assertTrue((folder / "movie.nfo").exists())
                self.assertTrue((folder / "Avatar.2009.srt").exists())
            finally:
                store.close()

    def test_watch_organize_tv_folder_moves_selected_subtitles_and_excludes_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            origin_path = root / "watch" / "tv"
            depot_path = root / "Depot"
            show = origin_path / "Example.Show.S01"
            show.mkdir(parents=True)
            for name in ["E01.mkv", "E01.srt", "E01.zh.srt", "show.nfo"]:
                (show / name).write_text("x", encoding="utf-8")
            store = Store(root / "state.sqlite")
            store.initialize()
            try:
                Depot = self._depot(depot_path, media_type=MediaType.TV)
                chain = self._watch_chain(store, Depot, ConfidenceLevel.HIGH)
                result = chain.process_origin(self._watch_origin(origin_path, depot_path, media_type=MediaType.TV))

                self.assertEqual(result.matched, 2)
                destination = depot_path / "Avatar (2009) {tmdb-19995}" / "Season 1"
                self.assertTrue((destination / "Avatar - S01E01.mkv").exists())
                self.assertTrue((destination / "Avatar - S01E01.srt").exists())
                self.assertTrue((show / "show.nfo").exists())
                self.assertTrue((show / "E01.srt").exists())
            finally:
                store.close()

    def test_watch_organize_tv_uses_resolution_planner(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            origin_path = root / "watch" / "tv"
            depot_path = root / "Depot"
            show = origin_path / "Example.Show"
            show.mkdir(parents=True)
            (show / "UglyNameA.mkv").write_text("x", encoding="utf-8")
            store = Store(root / "state.sqlite")
            store.initialize()
            try:
                matcher = FallbackTVMatcher()
                Depot = self._depot(depot_path, media_type=MediaType.TV)
                chain = WatchOrganizeRun(
                    matcher=matcher,
                    organizer=OrganizeExecutor(
                        locks=DepotLockRegistry(),
                        activity=ActivityRecorder(store),
                        sidecar_extensions=TEST_MEDIA_EXTENSIONS.sidecar,
                    ),
                    activity=ActivityRecorder(store),
                    extensions=TEST_MEDIA_EXTENSIONS,
                    depot_resolver=lambda _path: Depot,
                )

                result = chain.process_origin(self._watch_origin(origin_path, depot_path, media_type=MediaType.TV))

                self.assertEqual(matcher.extractor.requested_keys, ["UglyNameA.mkv"])
                self.assertEqual(result.matched, 1)
                self.assertTrue(
                    (
                        depot_path
                        / "Example Show (2020) {tmdb-1}"
                        / "Season 2"
                        / "Example Show - S02E07 - Corrected.mkv"
                    ).exists()
                )
                self.assertEqual(store.list_activity_events()[0].context["tv_resolution_status"], "applied")
            finally:
                store.close()

    def test_unknown_path_is_ignored_until_user_moves_item_out(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "watch"
            origin_path = root / "auto"
            unknown_path = origin_path / ".unknown"
            unknown_path.mkdir(parents=True)
            worker = self._watch_worker(root, origin_path)
            (unknown_path / "retry.mkv").write_text("x", encoding="utf-8")
            (origin_path / "retry.mkv").write_text("x", encoding="utf-8")

            self.assertIsNone(worker.dispatch_for_path(unknown_path / "retry.mkv"))
            self.assertIsNotNone(worker.dispatch_for_path(origin_path / "retry.mkv"))

    def test_watch_service_starts_singleton_and_processes_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            watch_settings_path = root / "watch"
            origin_path = watch_settings_path / "auto"
            depot_path = root / "Depot"
            origin_path.mkdir(parents=True)
            (origin_path / "Avatar.mkv").write_text("movie", encoding="utf-8")
            store = Store(root / "state.sqlite")
            store.initialize()
            try:
                Depot = self._depot(depot_path)
                configuration = FakeConfiguration(
                    WatchSettings(path=watch_settings_path, enabled=True),
                    [self._watch_origin(origin_path, depot_path)],
                    [Depot],
                    store,
                )
                service = WatchService(
                    configuration=configuration,
                    matcher=FakeMatcher(ConfidenceLevel.HIGH),
                    organizer=OrganizeExecutor(
                        locks=DepotLockRegistry(),
                        activity=ActivityRecorder(store),
                        sidecar_extensions=TEST_MEDIA_EXTENSIONS.sidecar,
                    ),
                    activity=ActivityRecorder(store),
                    extensions=TEST_MEDIA_EXTENSIONS,
                    poll_interval_seconds=999,
                    debounce_seconds=0,
                )

                service.start()
                worker = service.worker
                self.assertIsNotNone(worker)
                service.process_ready_once()
                self.assertIs(service.worker, worker)
                service.stop()

                self.assertIsNone(service.worker)
                self.assertTrue((depot_path / "Avatar (2009) {tmdb-19995}" / "Avatar (2009).mkv").exists())
            finally:
                store.close()

    def test_watch_start_stop_restart_updates_runtime_status_and_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            watch_settings_path = root / "watch"
            origin_path = watch_settings_path / "auto"
            depot_path = root / "Depot"
            origin_path.mkdir(parents=True)
            (origin_path / "Avatar.mkv").write_text("movie", encoding="utf-8")
            store = Store(root / "state.sqlite")
            store.initialize()
            try:
                Depot = self._depot(depot_path)
                configuration = FakeConfiguration(
                    WatchSettings(path=watch_settings_path, enabled=False),
                    [self._watch_origin(origin_path, depot_path)],
                    [Depot],
                    store,
                )
                service = WatchService(
                    configuration=configuration,
                    matcher=FakeMatcher(ConfidenceLevel.HIGH),
                    organizer=OrganizeExecutor(
                        locks=DepotLockRegistry(),
                        activity=ActivityRecorder(store),
                        sidecar_extensions=TEST_MEDIA_EXTENSIONS.sidecar,
                    ),
                    activity=ActivityRecorder(store),
                    extensions=TEST_MEDIA_EXTENSIONS,
                    poll_interval_seconds=999,
                    debounce_seconds=0,
                )

                started = service.start_watch()
                service.process_ready_once()
                self.assertEqual(started.state, "running")
                self.assertTrue(configuration.get_watch_settings().enabled)
                self.assertTrue((depot_path / "Avatar (2009) {tmdb-19995}" / "Avatar (2009).mkv").exists())

                restarted = service.restart_watch()
                self.assertEqual(restarted.state, "running")
                self.assertTrue(configuration.get_watch_settings().enabled)

                stopped = service.stop_watch()
                self.assertEqual(stopped.state, "stopped")
                self.assertFalse(configuration.get_watch_settings().enabled)
            finally:
                service.stop()
                store.close()

    def test_watch_buffer_dedupes_by_candidate_and_keeps_event_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "watch"
            origin_path = root / "auto"
            folder = origin_path / "Avatar.2009"
            folder.mkdir(parents=True)
            video = folder / "Avatar.2009.mkv"
            sidecar = folder / "movie.nfo"
            video.write_text("video", encoding="utf-8")
            sidecar.write_text("sidecar", encoding="utf-8")
            worker = self._watch_worker(root, origin_path)

            first = worker.handle_event(video, event_type="added", now=100)
            second = worker.handle_event(sidecar, event_type="modified", now=100.25)

            self.assertEqual(first.candidate_path, folder)
            self.assertEqual(second.candidate_path, folder)
            self.assertEqual(worker.flush_ready(now=100.75), [])
            ready = worker.flush_ready(now=101.5)

            self.assertEqual(len(ready), 1)
            self.assertEqual(ready[0].candidate_path, folder)
            self.assertEqual({path.name for path in ready[0].event_paths}, {"Avatar.2009.mkv", "movie.nfo"})
            self.assertEqual(ready[0].event_type, "modified")
            self.assertEqual(ready[0].stability_snapshot_count, 2)

    def test_watch_buffer_waits_for_candidate_snapshot_stability(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "watch"
            origin_path = root / "auto"
            origin_path.mkdir(parents=True)
            movie = origin_path / "Avatar.mkv"
            movie.write_text("x", encoding="utf-8")
            worker = self._watch_worker(root, origin_path)

            self.assertIsNotNone(worker.handle_event(movie, now=100))
            movie.write_text("larger file", encoding="utf-8")

            self.assertEqual(worker.flush_ready(now=101.1), [])
            self.assertEqual(worker.flush_ready(now=101.5), [])
            ready = worker.flush_ready(now=102.2)

            self.assertEqual(len(ready), 1)
            self.assertEqual(ready[0].candidate_path, movie)
            self.assertEqual(ready[0].stability_retry_count, 1)

    def test_watch_buffer_waits_for_folder_companion_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "watch"
            origin_path = root / "auto"
            folder = origin_path / "Avatar.2009"
            folder.mkdir(parents=True)
            video = folder / "Avatar.2009.mkv"
            video.write_text("video", encoding="utf-8")
            worker = self._watch_worker(root, origin_path)

            self.assertIsNotNone(worker.handle_event(video, now=100))
            (folder / "Avatar.2009.srt").write_text("subtitle", encoding="utf-8")

            self.assertEqual(worker.flush_ready(now=101.1), [])
            ready = worker.flush_ready(now=102.2)

            self.assertEqual(len(ready), 1)
            self.assertEqual(ready[0].candidate_path, folder)
            self.assertEqual(ready[0].stability_snapshot_count, 2)

    def test_watch_buffer_filters_boundaries_disabled_origins_and_delete_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "watch"
            movie_origin_path = root / "movies"
            disabled_origin_path = root / "disabled"
            tv_origin_path = root / "tv"
            for path in [movie_origin_path, disabled_origin_path, tv_origin_path, root / "other"]:
                path.mkdir(parents=True)
            valid_movie = movie_origin_path / "Valid.mkv"
            valid_movie.write_text("video", encoding="utf-8")
            (movie_origin_path / "Valid.srt").write_text("subtitle", encoding="utf-8")
            (disabled_origin_path / "Disabled.mkv").write_text("video", encoding="utf-8")
            (tv_origin_path / "Loose.S01E01.mkv").write_text("video", encoding="utf-8")
            (root / "root.mkv").write_text("video", encoding="utf-8")
            (root / "other" / "Other.mkv").write_text("video", encoding="utf-8")
            disabled_origin = Origin(
                id="disabled",
                name="Disabled",
                path=disabled_origin_path,
                media_type=MediaType.MOVIE,
                trigger=OriginTrigger.WATCH,
                policy=OrganizePolicy(target_depot_id="Depot"),
                enabled=False,
            )
            tv_origin = self._watch_origin(tv_origin_path, Path("C:/Depot"), media_type=MediaType.TV)
            worker = WatchEventBuffer(
                watch_settings=WatchSettings(path=root),
                origins=[
                    self._watch_origin(movie_origin_path, Path("C:/Depot")),
                    disabled_origin,
                    tv_origin,
                ],
                extensions=TEST_MEDIA_EXTENSIONS,
                debounce_seconds=1,
            )

            self.assertIsNone(worker.handle_event(valid_movie, event_type="deleted", now=100))
            self.assertIsNone(worker.handle_event(movie_origin_path / "Valid.srt", now=100))
            self.assertIsNone(worker.handle_event(disabled_origin_path / "Disabled.mkv", now=100))
            self.assertIsNone(worker.handle_event(tv_origin_path / "Loose.S01E01.mkv", now=100))
            self.assertIsNone(worker.handle_event(root / "root.mkv", now=100))
            self.assertIsNone(worker.handle_event(root / "other" / "Other.mkv", now=100))

    def test_watch_backlog_enqueues_one_dispatch_per_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "watch"
            origin_path = root / "auto"
            folder = origin_path / "Avatar.2009"
            unknown = origin_path / ".unknown"
            folder.mkdir(parents=True)
            unknown.mkdir()
            (folder / "Avatar.2009.mkv").write_text("video", encoding="utf-8")
            (folder / "Avatar.2009.srt").write_text("subtitle", encoding="utf-8")
            (origin_path / "Dune.2021.mkv").write_text("video", encoding="utf-8")
            (unknown / "Ignored.mkv").write_text("video", encoding="utf-8")

            backlog = self._watch_worker(root, origin_path).start(now=100)

            self.assertEqual({item.candidate_path.name for item in backlog}, {"Avatar.2009", "Dune.2021.mkv"})
            self.assertEqual(len(backlog), 2)
            self.assertEqual({item.source for item in backlog}, {"service_start_backlog"})

    def test_new_enabled_watch_origin_enqueues_backlog_without_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "watch"
            root.mkdir(parents=True)
            origin_path = root / "new"
            origin_path.mkdir()
            (origin_path / "Avatar.mkv").write_text("video", encoding="utf-8")
            worker = WatchEventBuffer(
                watch_settings=WatchSettings(path=root),
                origins=[],
                extensions=TEST_MEDIA_EXTENSIONS,
                debounce_seconds=1,
            )

            worker.start(now=100)
            backlog = worker.update_origin(self._watch_origin(origin_path, Path("C:/Depot")))

            self.assertEqual(len(backlog), 1)
            self.assertEqual(backlog[0].candidate_path, origin_path / "Avatar.mkv")
            self.assertEqual(backlog[0].source, "origin_enabled_backlog")

    def test_watch_running_state_keeps_new_events_for_next_debounce_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "watch"
            origin_path = root / "auto"
            origin_path.mkdir(parents=True)
            movie = origin_path / "Avatar.mkv"
            movie.write_text("video", encoding="utf-8")
            worker = self._watch_worker(root, origin_path)

            worker.begin_processing()
            self.assertIsNotNone(worker.handle_event(movie, now=100))
            self.assertEqual(worker.flush_ready(now=200), [])

            worker.finish_processing()
            ready = worker.flush_ready(now=201)

            self.assertEqual(len(ready), 1)
            self.assertEqual(ready[0].candidate_path, movie)

    def test_watch_activity_context_distinguishes_live_and_backlog_dispatches(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            watch = root / "watch"
            origin_path = watch / "auto"
            depot_path = root / "Depot"
            origin_path.mkdir(parents=True)
            live_movie = origin_path / "Live.mkv"
            live_movie.write_text("movie", encoding="utf-8")
            store = Store(root / "state.sqlite")
            store.initialize()
            try:
                Depot = self._depot(depot_path)
                chain = self._watch_chain(store, Depot, ConfidenceLevel.HIGH)
                worker = self._watch_worker(watch, origin_path)

                worker.handle_event(live_movie, now=100)
                chain.process_dispatches(worker.flush_ready(now=102))
                live_context = store.list_activity_events()[0].context

                backlog_movie = origin_path / "Backlog.mkv"
                backlog_movie.write_text("movie", encoding="utf-8")
                worker.enqueue_dispatches(worker.service_start_backlog(), now=200)
                chain.process_dispatches(worker.flush_ready(now=202))
                backlog_context = store.list_activity_events()[0].context

                self.assertEqual(live_context["watch_dispatch_source"], "live")
                self.assertEqual(live_context["watch_event_relative_path"], "Live.mkv")
                self.assertEqual(live_context["watch_candidate_relative_path"], "Live.mkv")
                self.assertEqual(backlog_context["watch_dispatch_source"], "service_start_backlog")
                self.assertEqual(backlog_context["watch_candidate_relative_path"], "Backlog.mkv")
            finally:
                store.close()

    def test_unrelated_live_event_does_not_retry_skipped_movie_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            origin_path = root / "watch" / "auto"
            depot_path = root / "Depot"
            destination = depot_path / "Avatar (2009) {tmdb-19995}"
            destination.mkdir(parents=True)
            (destination / "Avatar (2009).mkv").write_text("existing", encoding="utf-8")
            origin_path.mkdir(parents=True)
            stale = origin_path / "Avatar.mkv"
            stale.write_text("movie", encoding="utf-8")
            unrelated = origin_path / "Other.mkv"
            unrelated.write_text("movie", encoding="utf-8")
            store = Store(root / "state.sqlite")
            store.initialize()
            try:
                matcher = RecordingMatcher(ConfidenceLevel.HIGH)
                Depot = self._depot(depot_path)
                chain = self._watch_chain_with_matcher(store, Depot, matcher)
                origin = self._watch_origin(origin_path, depot_path)
                worker = self._watch_worker(root / "watch", origin_path)

                chain.process_dispatches([worker.dispatch_for_path(stale)])
                self.assertTrue(stale.exists())
                self.assertEqual(store.list_activity_events()[-1].context["skip_reason"], "movie_origin_depot_resolve_disabled")

                matcher.seen.clear()
                chain.process_dispatches([worker.dispatch_for_path(unrelated)])

                self.assertEqual(matcher.seen, ["Other"])
                self.assertTrue(stale.exists())
                self.assertEqual(len(store.list_activity_events()), 2)
                self.assertEqual(origin.id, "auto")
            finally:
                store.close()

    def test_same_candidate_live_event_may_retry_skipped_movie_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            origin_path = root / "watch" / "auto"
            depot_path = root / "Depot"
            destination = depot_path / "Avatar (2009) {tmdb-19995}"
            destination.mkdir(parents=True)
            (destination / "Avatar (2009).mkv").write_text("existing", encoding="utf-8")
            origin_path.mkdir(parents=True)
            stale = origin_path / "Avatar.mkv"
            stale.write_text("movie", encoding="utf-8")
            store = Store(root / "state.sqlite")
            store.initialize()
            try:
                matcher = RecordingMatcher(ConfidenceLevel.HIGH)
                Depot = self._depot(depot_path)
                chain = self._watch_chain_with_matcher(store, Depot, matcher)
                worker = self._watch_worker(root / "watch", origin_path)

                chain.process_dispatches([worker.dispatch_for_path(stale)])
                chain.process_dispatches([worker.dispatch_for_path(stale)])

                self.assertEqual(matcher.seen, ["Avatar", "Avatar"])
                self.assertTrue(stale.exists())
                self.assertEqual(len(store.list_activity_events()), 2)
            finally:
                store.close()

    def test_backlog_may_retry_skipped_movie_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            watch_root = root / "watch"
            origin_path = watch_root / "auto"
            depot_path = root / "Depot"
            destination = depot_path / "Avatar (2009) {tmdb-19995}"
            destination.mkdir(parents=True)
            (destination / "Avatar (2009).mkv").write_text("existing", encoding="utf-8")
            origin_path.mkdir(parents=True)
            stale = origin_path / "Avatar.mkv"
            stale.write_text("movie", encoding="utf-8")
            store = Store(root / "state.sqlite")
            store.initialize()
            try:
                matcher = RecordingMatcher(ConfidenceLevel.HIGH)
                Depot = self._depot(depot_path)
                chain = self._watch_chain_with_matcher(store, Depot, matcher)
                worker = self._watch_worker(watch_root, origin_path)

                chain.process_dispatches([worker.dispatch_for_path(stale)])
                matcher.seen.clear()
                chain.process_dispatches(worker.start(now=100))

                self.assertEqual(matcher.seen, ["Avatar"])
                entries = store.list_activity_events()
                self.assertEqual(len(entries), 2)
                self.assertIn("service_start_backlog", {entry.context["watch_dispatch_source"] for entry in entries})
            finally:
                store.close()

    def test_watch_returns_rejected_small_standalone_movie_video(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            origin_path = root / "watch" / "auto"
            depot_path = root / "Depot"
            origin_path.mkdir(parents=True)
            small = origin_path / "Sample.mkv"
            small.write_bytes(b"x")
            store = Store(root / "state.sqlite")
            store.initialize()
            try:
                Depot = self._depot(depot_path)
                chain = self._watch_chain(
                    store,
                    Depot,
                    ConfidenceLevel.HIGH,
                    min_non_subtitle_file_size_bytes=10,
                )

                result = chain.process_origin(self._watch_origin(origin_path, depot_path))

                self.assertEqual(result.unmatched, 1)
                self.assertFalse(small.exists())
                self.assertTrue((origin_path / ".unknown" / "Sample.mkv").exists())
                event = store.list_activity_events()[0]
                self.assertEqual(event.reason, "below_min_non_subtitle_file_size")
                self.assertEqual(event.context["rejected_source_package_reason"], "below_min_non_subtitle_file_size")
            finally:
                store.close()

    def test_watch_returns_rejected_small_folder_preserves_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            origin_path = root / "watch" / "auto"
            depot_path = root / "Depot"
            nested = origin_path / "Ads" / "nested"
            nested.mkdir(parents=True)
            (origin_path / "Ads" / "sample.mkv").write_bytes(b"x")
            (nested / "ad.mkv").write_bytes(b"x")
            store = Store(root / "state.sqlite")
            store.initialize()
            try:
                Depot = self._depot(depot_path)
                chain = self._watch_chain(
                    store,
                    Depot,
                    ConfidenceLevel.HIGH,
                    min_non_subtitle_file_size_bytes=10,
                )

                result = chain.process_origin(self._watch_origin(origin_path, depot_path))

                self.assertEqual(result.unmatched, 1)
                self.assertFalse((origin_path / "Ads").exists())
                self.assertTrue((origin_path / ".unknown" / "Ads" / "sample.mkv").exists())
                self.assertTrue((origin_path / ".unknown" / "Ads" / "nested" / "ad.mkv").exists())
                self.assertEqual(store.list_activity_events()[0].reason, "below_min_non_subtitle_file_size")
            finally:
                store.close()

    def test_watch_returns_rejected_sidecar_only_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            origin_path = root / "watch" / "auto"
            depot_path = root / "Depot"
            sidecars = origin_path / "Sidecars"
            sidecars.mkdir(parents=True)
            (sidecars / "movie.nfo").write_text("metadata", encoding="utf-8")
            (sidecars / "poster.jpg").write_text("poster", encoding="utf-8")
            store = Store(root / "state.sqlite")
            store.initialize()
            try:
                Depot = self._depot(depot_path)
                chain = self._watch_chain(store, Depot, ConfidenceLevel.HIGH)

                result = chain.process_origin(self._watch_origin(origin_path, depot_path))

                self.assertEqual(result.unmatched, 1)
                self.assertFalse(sidecars.exists())
                self.assertTrue((origin_path / ".unknown" / "Sidecars" / "movie.nfo").exists())
                event = store.list_activity_events()[0]
                self.assertEqual(event.reason, "sidecar_only")
                self.assertEqual(event.context["destination_relative_path"], ".unknown/Sidecars")
            finally:
                store.close()

    def test_watch_ignores_root_sidecar_files_for_live_and_backlog(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "watch"
            origin_path = root / "auto"
            origin_path.mkdir(parents=True)
            sidecar = origin_path / "loose.nfo"
            sidecar.write_text("metadata", encoding="utf-8")
            worker = self._watch_worker(
                root,
                origin_path,
                min_non_subtitle_file_size_bytes=10,
            )

            self.assertIsNone(worker.dispatch_for_path(sidecar))
            self.assertEqual(worker.start(now=100), [])

    def _watch_origin(self, origin_path: Path, depot_path: Path, *, media_type: MediaType = MediaType.MOVIE) -> Origin:
        return Origin(
            id="auto",
            name="Auto",
            path=origin_path,
            media_type=media_type,
            trigger=OriginTrigger.WATCH,
            policy=OrganizePolicy(target_depot_id="Depot"),
        )

    def _depot(self, depot_path: Path, *, media_type: MediaType = MediaType.MOVIE) -> Depot:
        return Depot(
            id="Depot",
            name="Depot",
            path=depot_path,
            media_type=media_type,
            policy=TransferPolicy(target_library_path=depot_path.parent / "library"),
        )

    def _watch_worker(
        self,
        root: Path,
        origin_path: Path,
        *,
        min_non_subtitle_file_size_bytes: int | None = None,
    ) -> WatchEventBuffer:
        return WatchEventBuffer(
            watch_settings=WatchSettings(path=root),
            origins=[self._watch_origin(origin_path, Path("C:/Depot"))],
            extensions=TEST_MEDIA_EXTENSIONS,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
            debounce_seconds=1,
        )

    def _watch_chain(
        self,
        store: Store,
        Depot: Depot,
        confidence: ConfidenceLevel,
        *,
        min_non_subtitle_file_size_bytes: int | None = None,
    ) -> WatchOrganizeRun:
        return self._watch_chain_with_matcher(
            store,
            Depot,
            FakeMatcher(confidence),
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )

    def _watch_chain_with_matcher(
        self,
        store: Store,
        Depot: Depot,
        matcher,
        *,
        min_non_subtitle_file_size_bytes: int | None = None,
    ) -> WatchOrganizeRun:
        return WatchOrganizeRun(
            matcher=matcher,
            organizer=OrganizeExecutor(
                locks=DepotLockRegistry(),
                activity=ActivityRecorder(store),
                sidecar_extensions=TEST_MEDIA_EXTENSIONS.sidecar,
                subtitle_extensions=TEST_MEDIA_EXTENSIONS.subtitle,
                extensions=TEST_MEDIA_EXTENSIONS,
                min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
            ),
            activity=ActivityRecorder(store),
            extensions=TEST_MEDIA_EXTENSIONS,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
            depot_resolver=lambda _path: Depot,
        )


class FakeMatcher:
    def __init__(self, confidence: ConfidenceLevel):
        self.confidence = confidence

    def match(self, candidate):
        high = self.confidence == ConfidenceLevel.HIGH
        return MatchResult(
            candidate_id=candidate.id,
            media_type=candidate.media_type,
            confidence=self.confidence,
            title="Avatar" if high else None,
            year=2009 if high else None,
            tmdb_id=19995 if high else None,
            metadata={"title": "Avatar", "release_year": 2009, "tmdb_id": 19995} if high else {},
        )


class RecordingMatcher(FakeMatcher):
    def __init__(self, confidence: ConfidenceLevel):
        super().__init__(confidence)
        self.seen: list[str] = []

    def match(self, candidate):
        self.seen.append(candidate.display_name)
        return super().match(candidate)


class FallbackTVMatcher:
    def __init__(self):
        self.extractor = FakeTVEpisodeExtractor(
            {"UglyNameA.mkv": {"season": 2, "episode": 7, "end_episode": None}}
        )
        self.tv_episode_planner = TVEpisodePlanner(
            extensions=TEST_MEDIA_EXTENSIONS,
            episode_extractor=self.extractor,
            episode_catalog_provider=FakeTVEpisodeCatalogProvider(TVEpisodeCatalog({2: {7: "Corrected"}})),
        )

    def match(self, candidate):
        return MatchResult(
            candidate_id=candidate.id,
            media_type=MediaType.TV,
            confidence=ConfidenceLevel.HIGH,
            title="Example Show",
            year=2020,
            tmdb_id=1,
            metadata={"title": "Example Show", "release_year": 2020, "tmdb_id": 1},
        )


class FakeConfiguration:
    def __init__(self, watch_settings, origins, depots, store):
        self.watch_settings = watch_settings
        self.origins = origins
        self.depots = depots
        self.store = store

    def get_watch_settings(self):
        return self.watch_settings

    def save_watch_settings(self, config):
        self.watch_settings = config
        self.store.save_watch_settings(config)
        return config


    def list_origins(self):
        return self.origins

    def list_depots(self):
        return self.depots

    def get_depot(self, depot_id):
        for depot in self.depots:
            if depot.id == depot_id:
                return depot
        raise ConfigurationError("missing Depot")


if __name__ == "__main__":
    unittest.main()
