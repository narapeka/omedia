from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from app.api.cli.main import run_cli_json
from app.services.inventory.service import InventoryService
from app.domain.match import ConfidenceLevel
from app.domain.media import MediaType
from app.domain.origin import OriginTrigger
from app.domain.transfer import TransferStatus
from app.domain.origin import OrganizePolicy, Origin
from app.domain.depot import Depot, TransferPolicy
from app.domain.watch import WatchSettings
from app.domain.match import MatchResult
from app.domain.media import MediaExtensionPolicy
from app.domain.tv import TVEpisodeCatalog
from app.domain.transfer import TransferJob
from app.engines.plan.tv.planner import TVEpisodePlanner
from app.services.config.settings import SettingsFile
from app.services.organize.session import SessionBook
from app.services.organize.execute import OrganizeExecutionResult
from app.services.organize.service import OrganizeService
from app.services.transfer.worker import TransferExecutionResult, TransferRejected
from app.domain.transfer import TransferErrorCode
from app.core.error import ConfigurationError
from support import FakeTVEpisodeCatalogProvider, FakeTVEpisodeExtractor, TEST_MEDIA_EXTENSIONS


class ConfigFixture:
    def __init__(self, root: Path):
        self.watch_settings = WatchSettings(id="watch", path=root / "watch", enabled=True)
        self.depot = Depot(
            id="Depot",
            name="Movie staging",
            path=root / "Depot",
            media_type=MediaType.MOVIE,
            enabled=True,
            policy=TransferPolicy(target_library_path=root / "library"),
        )
        self.origin = Origin(
            id="manual",
            name="Manual movies",
            path=root / "origin",
            media_type=MediaType.MOVIE,
            trigger=OriginTrigger.MANUAL,
            enabled=True,
            policy=OrganizePolicy(target_depot_id=self.depot.id),
        )
        self.watch_origin = Origin(
            id="watch-movie",
            name="Watched movies",
            path=self.watch_settings.path / "watch-movie",
            media_type=MediaType.MOVIE,
            trigger=OriginTrigger.WATCH,
            enabled=True,
            policy=OrganizePolicy(target_depot_id=self.depot.id),
        )

    def list_origins(self):
        return [self.origin, self.watch_origin]

    def get_origin(self, origin_id):
        for origin in self.list_origins():
            if origin.id == origin_id:
                return origin
        raise ConfigurationError("missing origin")

    def list_depots(self):
        return [self.depot]

    def get_depot(self, depot_id):
        if depot_id == self.depot.id:
            return self.depot
        raise ConfigurationError("missing Depot")

    def get_watch_settings(self):
        return self.watch_settings


class FakeMatch:
    def match_batch(self, candidates):
        return {
            candidate.id: MatchResult(
                candidate_id=candidate.id,
                media_type=candidate.media_type,
                confidence=ConfidenceLevel.HIGH,
                title="Avatar",
                year=2009,
                tmdb_id=19995,
            )
            for candidate in candidates
        }


class FakeTVMatch:
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


class FakeOrganizer:
    def __init__(self):
        self.candidates = []

    def organize_candidates(self, candidates, Depot, **_kwargs):
        self.candidates = list(candidates)
        return OrganizeExecutionResult(moved=len(candidates), results=[])


class FakeTransferService:
    def __init__(self, *, busy=False):
        self.busy = busy
        self.executed = False

    def execute_depot(self, Depot, *, requested_by="manual"):
        if self.busy:
            raise TransferRejected(TransferErrorCode.TRANSFER_WORKER_BUSY, "busy")
        self.executed = True
        job = TransferJob(id="transfer-1", depot_id=Depot.id, status=TransferStatus.QUEUED, requested_by=requested_by)
        job.status = TransferStatus.SUCCEEDED
        return TransferExecutionResult(job=job, moved=1)


class FakeStore:
    def get_organize_rule(self, _rule_id):
        return None

    def get_transfer_rule(self, _rule_id):
        return None

    def list_transfer_jobs(self, limit=20):
        return [TransferJob(id="transfer-old", depot_id="Depot", status=TransferStatus.SUCCEEDED)]


class Services:
    def __init__(self, root: Path, *, busy=False, extensions=None):
        self.configuration = ConfigFixture(root)
        extensions = extensions or MediaExtensionPolicy(video=frozenset({".mkv"}), subtitle=frozenset(), sidecar=frozenset())
        self.startup_settings = SimpleNamespace(
            organize=SimpleNamespace(extensions=extensions, min_non_subtitle_file_size_bytes=None),
        )
        self.inventory = InventoryService(self.startup_settings.organize.extensions)
        self.match = FakeMatch()
        self.organizer = FakeOrganizer()
        self.transfer_service = FakeTransferService(busy=busy)
        self.store = FakeStore()
        self.organize_pipeline = OrganizeService(
            configuration=self.configuration,
            sessions=SessionBook(),
            settings=SettingsFile(root / "common.yaml", self.startup_settings),
            match=self.match,
            organizer=self.organizer,
            activity=None,
            store=self.store,
        )


class TVServices(Services):
    def __init__(self, root: Path):
        super().__init__(root, extensions=TEST_MEDIA_EXTENSIONS)
        self.configuration.depot = replace(self.configuration.depot, media_type=MediaType.TV)
        self.configuration.origin = replace(
            self.configuration.origin,
            path=root / "tv-origin",
            media_type=MediaType.TV,
            policy=OrganizePolicy(target_depot_id=self.configuration.depot.id),
        )
        self.match = FakeTVMatch()
        self.organize_pipeline.update_matcher(self.match)


class CLITests(unittest.TestCase):
    def test_origin_and_depot_discovery_use_disk_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._seed(root)
            services = Services(root)

            origin_code, origin_output = run_cli_json(["origin", "--origin", "manual"], services)
            depot_code, depot_output = run_cli_json(["depot", "--depot", "Depot"], services)

            self.assertEqual(origin_code, 0)
            origin_result = json.loads(origin_output)["result"]
            self.assertEqual(origin_result["name"], "Manual movies")
            self.assertEqual(origin_result["candidate_count"], 1)
            self.assertEqual(depot_code, 0)
            depot_result = json.loads(depot_output)["result"]
            self.assertEqual(depot_result["name"], "Movie staging")
            self.assertEqual(depot_result["pending_count"], 1)

    def test_origin_and_depot_selectors_accept_configured_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._seed(root)
            services = Services(root)

            origin_code, origin_output = run_cli_json(["origin", "--origin", str(root / "origin")], services)
            depot_code, depot_output = run_cli_json(["depot", "--depot", str(root / "Depot")], services)
            organize_code, organize_output = run_cli_json(["organize", "--origin", str(root / "origin")], services)
            transfer_code, transfer_output = run_cli_json(["transfer", "--depot", str(root / "Depot")], services)
            name_code, name_output = run_cli_json(["origin", "--origin", "Manual movies"], services)

            self.assertEqual(origin_code, 0)
            self.assertEqual(json.loads(origin_output)["result"]["id"], "manual")
            self.assertEqual(depot_code, 0)
            self.assertEqual(json.loads(depot_output)["result"]["id"], "Depot")
            self.assertEqual(organize_code, 0)
            self.assertEqual(json.loads(organize_output)["result"]["source"], "manual")
            self.assertEqual(transfer_code, 0)
            self.assertEqual(json.loads(transfer_output)["result"]["job"]["depot_id"], "Depot")
            self.assertEqual(name_code, 0)
            self.assertEqual(json.loads(name_output)["result"]["id"], "manual")

    def test_manual_and_ad_hoc_organize_accept_matched_candidates_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._seed(root)
            services = Services(root)

            manual_code, manual_output = run_cli_json(["organize", "--origin", "manual"], services)
            ad_hoc = root / "ad-hoc"
            ad_hoc.mkdir()
            (ad_hoc / "Avatar.mkv").write_text("x", encoding="utf-8")
            ad_hoc_code, ad_hoc_output = run_cli_json(
                ["organize", "--source", str(ad_hoc), "--depot", "Depot", "--type", "movie", "--bucket", "first-char"],
                services,
            )

            self.assertEqual(manual_code, 0)
            self.assertEqual(json.loads(manual_output)["result"]["matched"], 1)
            self.assertEqual(ad_hoc_code, 0)
            self.assertEqual(json.loads(ad_hoc_output)["result"]["moved"], 1)
            self.assertEqual(services.organizer.candidates[-1].preview.preview_bucket, "A")

    def test_cli_organize_includes_movie_subtitle_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._seed(root)
            (root / "origin" / "Avatar.mkv").unlink()
            movie = root / "origin" / "Avatar.2009"
            movie.mkdir()
            for name in ["Avatar.2009.mkv", "Avatar.2009.zh.srt", "Avatar.2009.sup", "movie.nfo"]:
                (movie / name).write_text("x", encoding="utf-8")
            services = Services(root, extensions=TEST_MEDIA_EXTENSIONS)

            code, output = run_cli_json(["organize", "--origin", "manual"], services)

            self.assertEqual(code, 0)
            result = json.loads(output)["result"]
            self.assertEqual(result["matched"], 3)
            self.assertEqual(
                {candidate.source_path.name for candidate in services.organizer.candidates},
                {"Avatar.2009.mkv", "Avatar.2009.zh.srt", "Avatar.2009.sup"},
            )

    def test_cli_tv_organize_uses_resolution_planner(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for folder in ["watch", "Depot", "library", "tv-origin"]:
                (root / folder).mkdir(parents=True, exist_ok=True)
            show = root / "tv-origin" / "Example.Show"
            show.mkdir()
            (show / "UglyNameA.mkv").write_text("x", encoding="utf-8")
            services = TVServices(root)

            code, output = run_cli_json(["organize", "--origin", "manual"], services)

            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output)["result"]["matched"], 1)
            self.assertEqual(services.match.extractor.requested_keys, ["UglyNameA.mkv"])
            self.assertEqual(
                services.organizer.candidates[0].preview.proposed_relative_path,
                Path("Example Show (2020) {tmdb-1}/Season 2/Example Show - S02E07 - Corrected.mkv"),
            )

    def test_transfer_command_blocks_until_job_finishes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._seed(root)
            services = Services(root)

            code, output = run_cli_json(["transfer", "--depot", "Depot"], services)

            self.assertEqual(code, 0)
            self.assertTrue(services.transfer_service.executed)
            self.assertEqual(json.loads(output)["result"]["job"]["status"], "succeeded")

    def test_validation_errors_cover_refactor_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._seed(root)
            services = Services(root)
            overlap = root / "origin"

            cases = [
                ["organize", "--origin", "manual", "--source", str(root / "other")],
                ["organize", "--origin", "manual", "--depot", "Depot"],
                ["organize", "--origin", "manual", "--type", "movie"],
                ["organize", "--origin", "manual", "--bucket", "none"],
                ["organize", "--origin", "watch-movie"],
                ["organize", "--source", str(overlap), "--depot", "Depot", "--type", "movie"],
                ["organize", "--source", str(root / "ad-hoc"), "--type", "movie"],
                ["organize", "--source", str(root / "ad-hoc"), "--depot", "Depot"],
            ]

            (root / "ad-hoc").mkdir()
            for command in cases:
                code, output = run_cli_json(command, services)
                self.assertEqual(code, 2, command)
                self.assertEqual(json.loads(output)["error"]["type"], "ConfigurationError")

    def test_transfer_busy_uses_omedia_error_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._seed(root)
            code, output = run_cli_json(["transfer", "--depot", "Depot"], Services(root, busy=True))

            self.assertEqual(code, 3)
            self.assertEqual(json.loads(output)["error"]["type"], "TransferRejected")

    def _seed(self, root: Path) -> None:
        for folder in ["watch", "origin", "Depot", "library"]:
            (root / folder).mkdir(parents=True, exist_ok=True)
        (root / "watch" / "watch-movie").mkdir(parents=True, exist_ok=True)
        (root / "origin" / "Avatar.mkv").write_text("x", encoding="utf-8")
        (root / "Depot" / "Ready.mkv").write_text("x", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
