from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from sqlalchemy import text

from app.domain.activity import ActivityAction, ActivityArea, ActivityEntityType, ActivityEvent, ActivityStatus
from app.domain.cache import TMDBDetailCache
from app.domain.media import MediaType
from app.domain.origin import OriginTrigger
from app.domain.transfer import TransferStatus, TransferTrigger
from app.domain.origin import OrganizePolicy, Origin
from app.domain.depot import Depot, TransferPolicy
from app.domain.watch import WatchSettings
from app.domain.match import TMDBCandidate, TMDBSearchPage, TMDBSearchResult
from app.domain.rule import OrganizeRule, RuleCondition, RuleOperator, RuleCategory, TransferRule
from app.domain.transfer import TransferJob
from app.infra.tmdb.metadata import TMDBMetadataService
from app.infra.tmdb.ttl import TTLCache
from support import RuntimeApiFixture, make_common_config


class FakeTMDBProvider:
    def __init__(self):
        self.calls = 0

    def get_by_id(self, media_type, tmdb_id):
        self.calls += 1
        return TMDBCandidate(tmdb_id, media_type, f"Title {self.calls}", year=2020)

    def search_page(self, media_type, title, year, language, page):
        return TMDBSearchPage(
            (TMDBSearchResult(99, media_type, f"{title} Search", year=year),),
            page=page,
            total_pages=1,
            total_results=1,
        )

    def load_candidate_details(self, media_type, tmdb_id, language, fallback_search_result):
        return fallback_search_result.to_candidate()

    def get_tv_episode_titles(self, tmdb_id, season_numbers, languages):
        return {}

    def get_tv_season_years(self, tmdb_id, season_numbers, languages):
        return {}


class AdminApiTests(unittest.TestCase):
    def test_admin_tmdb_clear_deletes_persistent_and_memory_cache(self) -> None:
        with self._app() as fixture:
            provider = FakeTMDBProvider()
            service = TMDBMetadataService(
                provider,
                store=fixture.runtime.store,
                search_cache=TTLCache(ttl_seconds=60, max_entries=10),
            )
            fixture.runtime.match.tmdb = service
            fixture.runtime.store.save_tmdb_detail(
                TMDBDetailCache(
                    media_type="movie",
                    tmdb_id=1,
                    metadata={"media_type": "movie", "tmdb_id": 1, "title": "Cached"},
                )
            )
            fixture.runtime.match.tmdb.get_by_id(MediaType.MOVIE, 2)
            fixture.runtime.match.tmdb.search_page(MediaType.MOVIE, "Avatar", 2009, "zh-CN", 1)
            self.assertEqual(service.cache_stats().entries, 1)

            response = fixture.client.post("/api/admin/cache/tmdb/clear")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["deleted_entries"], 2)
            self.assertIsNone(fixture.runtime.store.get_tmdb_detail("movie", 1))
            self.assertEqual(service.cache_stats().entries, 0)

    def test_admin_tmdb_clear_without_provider_deletes_persistent_cache(self) -> None:
        with self._app(tmdb_api_key="") as fixture:
            fixture.runtime.store.save_tmdb_detail(
                TMDBDetailCache(
                    media_type="movie",
                    tmdb_id=1,
                    metadata={"media_type": "movie", "tmdb_id": 1, "title": "Cached"},
                )
            )

            response = fixture.client.post("/api/admin/cache/tmdb/clear")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["deleted_entries"], 1)
            self.assertIsNone(fixture.runtime.store.get_tmdb_detail("movie", 1))

    def test_activity_prune_deletes_only_old_entries(self) -> None:
        with self._app() as fixture:
            old = datetime.now(timezone.utc) - timedelta(days=200)
            recent = datetime.now(timezone.utc) - timedelta(days=10)
            fixture.runtime.store.save_activity_event(_activity("old", old))
            fixture.runtime.store.save_activity_event(_activity("recent", recent))

            response = fixture.client.post("/api/admin/activity/prune")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["deleted_events"], 1)
            ids = [event.id for event in fixture.runtime.store.list_activity_events()]
            self.assertEqual(ids, ["recent"])

    def test_transfer_prune_deletes_old_terminal_history_only(self) -> None:
        with self._app() as fixture:
            depot = _depot(fixture.root, "Depot-a")
            fixture.runtime.store.save_depot(depot)
            old = datetime.now(timezone.utc) - timedelta(days=200)
            fixture.runtime.store.save_transfer_job(
                TransferJob(
                    id="job-old",
                    depot_id=depot.id,
                    status=TransferStatus.SUCCEEDED,
                    requested_by="test",
                    created_at=old,
                    finished_at=old,
                )
            )
            fixture.runtime.store.save_transfer_job(
                TransferJob(
                    id="job-running",
                    depot_id=depot.id,
                    status=TransferStatus.RUNNING,
                    requested_by="test",
                    created_at=old,
                )
            )

            response = fixture.client.post("/api/admin/transfer/prune")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["deleted_jobs"], 1)
            self.assertNotIn("deleted_batches", response.json())
            self.assertIsNone(fixture.runtime.store.get_transfer_job("job-old"))
            self.assertIsNotNone(fixture.runtime.store.get_transfer_job("job-running"))

    def test_backup_includes_config_providers_and_excludes_history(self) -> None:
        with self._app() as fixture:
            _seed_config(fixture.runtime, fixture.root)
            fixture.runtime.store.save_activity_event(_activity("history", datetime.now(timezone.utc)))
            fixture.runtime.store.save_tmdb_detail(
                TMDBDetailCache(media_type="movie", tmdb_id=1, metadata={"media_type": "movie", "tmdb_id": 1, "title": "Cached"})
            )

            response = fixture.client.get("/api/admin/backup")

            self.assertEqual(response.status_code, 200)
            data = yaml.safe_load(response.text)
            self.assertEqual(data["format"], "omedia-config-backup")
            self.assertEqual(data["version"], 2)
            self.assertEqual(
                data["organize"],
                {
                    "extensions": {"video": [".mkv"], "subtitle": [".srt"], "sidecar": [".nfo"]},
                    "min_non_subtitle_file_size_mb": 50,
                },
            )
            self.assertEqual(
                data["providers"],
                {
                    "tmdb": {
                        "api_key": "tmdb-secret",
                        "base_url": "https://api.themoviedb.org/3",
                        "rate_limit": 10.0,
                        "proxy": None,
                    },
                    "llm": {
                        "api_key": "llm-secret",
                        "base_url": "https://llm.example/v1/",
                        "model": "gpt-test",
                        "batch_size": 3,
                        "rate_limit": 1.0,
                        "proxy": None,
                    },
                },
            )
            self.assertNotIn("media_extensions", data)
            self.assertEqual(data["watch_runtime"], {"poll_interval_seconds": 15.0, "stability_debounce_seconds": 30.0})
            self.assertIn("watch_settings", data)
            self.assertNotIn("watch_config", data)
            self.assertEqual(len(data["origins"]), 1)
            self.assertEqual(len(data["depots"]), 1)
            self.assertIn("resolve_mode", data["depots"][0])
            self.assertNotIn("overwrite_mode", data["depots"][0])
            self.assertEqual(len(data["organize_rules"]), 1)
            self.assertEqual(len(data["transfer_rules"]), 1)
            self.assertNotIn("history", response.text)
            self.assertNotIn("movie:1", response.text)

    def test_restore_validates_before_deleting_existing_records(self) -> None:
        with self._app() as fixture:
            _seed_config(fixture.runtime, fixture.root)
            fixture.runtime.store.save_activity_event(_activity("history", datetime.now(timezone.utc)))

            response = fixture.client.post("/api/admin/restore", json={"content": "not: [valid"})

            self.assertEqual(response.status_code, 400)
            self.assertEqual(len(fixture.runtime.store.list_origins()), 1)
            self.assertEqual(len(fixture.runtime.store.list_activity_events()), 1)

    def test_restore_rejects_wrong_backup_version_before_deleting_existing_records(self) -> None:
        with self._app() as fixture:
            _seed_config(fixture.runtime, fixture.root)
            fixture.runtime.store.save_activity_event(_activity("history", datetime.now(timezone.utc)))
            backup = _backup_payload(fixture.root, suffix="new")
            backup["version"] = 1

            response = fixture.client.post("/api/admin/restore", json={"content": yaml.safe_dump(backup, sort_keys=False)})

            self.assertEqual(response.status_code, 400)
            self.assertIn("version", response.json()["error"]["message"])
            self.assertEqual(len(fixture.runtime.store.list_origins()), 1)
            self.assertEqual(len(fixture.runtime.store.list_activity_events()), 1)

    def test_restore_rejects_broken_reference_before_deleting_existing_records(self) -> None:
        with self._app() as fixture:
            _seed_config(fixture.runtime, fixture.root)
            fixture.runtime.store.save_activity_event(_activity("history", datetime.now(timezone.utc)))
            backup = _backup_payload(fixture.root, suffix="new")
            backup["origins"][0]["policy"]["target_depot_id"] = "missing-depot"

            response = fixture.client.post("/api/admin/restore", json={"content": yaml.safe_dump(backup, sort_keys=False)})

            self.assertEqual(response.status_code, 400)
            self.assertIn("unknown Depot", response.json()["error"]["message"])
            self.assertEqual(len(fixture.runtime.store.list_origins()), 1)
            self.assertEqual(len(fixture.runtime.store.list_activity_events()), 1)

    def test_restore_replaces_config_clears_history_and_preserves_schema_metadata(self) -> None:
        with self._app() as fixture:
            _seed_config(fixture.runtime, fixture.root, suffix="old")
            fixture.runtime.store.save_activity_event(_activity("history", datetime.now(timezone.utc)))
            fixture.runtime.store.save_tmdb_detail(
                TMDBDetailCache(media_type="movie", tmdb_id=1, metadata={"media_type": "movie", "tmdb_id": 1, "title": "Cached"})
            )
            backup = _backup_payload(fixture.root, suffix="new")

            response = fixture.client.post("/api/admin/restore", json={"content": yaml.safe_dump(backup, sort_keys=False)})

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body["restored"]["origins"], 1)
            self.assertEqual(body["cleared"]["activity_events"], 1)
            self.assertEqual(body["cleared"]["tmdb_detail_cache"], 1)
            self.assertEqual([origin.id for origin in fixture.runtime.store.list_origins()], ["origin-new"])
            self.assertEqual([depot.id for depot in fixture.runtime.store.list_depots()], ["Depot-new"])
            self.assertEqual(fixture.runtime.store.list_activity_events(), [])
            self.assertIsNone(fixture.runtime.store.get_tmdb_detail("movie", 1))
            self.assertEqual(fixture.runtime.startup_settings.organize.extensions.video, frozenset({".mkv", ".mp4"}))
            self.assertEqual(fixture.runtime.startup_settings.organize.min_non_subtitle_file_size_mb, 75)
            self.assertEqual(fixture.runtime.startup_settings.providers.tmdb_api_key, "tmdb-new")
            self.assertEqual(fixture.runtime.startup_settings.providers.tmdb_base_url, "https://tmdb.example/3")
            self.assertEqual(fixture.runtime.startup_settings.providers.tmdb_rate_limit, 2.5)
            self.assertEqual(fixture.runtime.startup_settings.providers.tmdb_proxy, "http://127.0.0.1:10809")
            self.assertEqual(fixture.runtime.startup_settings.providers.llm_api_key, "llm-new")
            self.assertEqual(fixture.runtime.startup_settings.providers.llm_base_url, "https://llm.restore/v1/")
            self.assertEqual(fixture.runtime.startup_settings.providers.llm_model, "gpt-restore")
            self.assertEqual(fixture.runtime.startup_settings.providers.llm_batch_size, 8)
            self.assertEqual(fixture.runtime.startup_settings.providers.llm_rate_limit, 0.5)
            self.assertEqual(fixture.runtime.startup_settings.providers.llm_proxy, "http://proxy.local:8080")
            self.assertEqual(fixture.runtime.match.settings.providers.tmdb_api_key, "tmdb-new")
            self.assertEqual(fixture.runtime.startup_settings.watch.poll_interval_seconds, 7.0)
            self.assertEqual(fixture.runtime.startup_settings.watch.stability_debounce_seconds, 19.0)
            self.assertEqual(fixture.runtime.watch_automation.poll_interval_seconds, 7.0)
            self.assertEqual(fixture.runtime.watch_automation.debounce_seconds, 19.0)
            common = yaml.safe_load(fixture.common_path.read_text(encoding="utf-8"))
            self.assertEqual(common["tmdb"]["api_key"], "tmdb-new")
            self.assertEqual(common["llm"]["api_key"], "llm-new")
            with fixture.runtime.store.session_factory() as session:
                version = session.execute(text("select version_num from alembic_version")).scalar_one()
            self.assertEqual(version, "0001_initial_schema")

    def _app(self, *, tmdb_api_key: str = "tmdb-secret"):
        return RuntimeApiFixture(
            common=make_common_config(
                min_non_subtitle_file_size_mb=50,
                tmdb={"api_key": tmdb_api_key},
                llm={
                    "api_key": "llm-secret",
                    "base_url": "https://llm.example/v1/",
                    "model": "gpt-test",
                    "batch_size": 3,
                },
            )
        )


def _seed_config(runtime, root: Path, *, suffix: str = "a") -> None:
    runtime.store.save_watch_settings(WatchSettings(path=root / f"watch-{suffix}", enabled=True))
    runtime.store.save_organize_rule(_organize_rule(suffix))
    runtime.store.save_transfer_rule(_transfer_rule(suffix))
    runtime.store.save_origin(_origin(root, suffix))
    runtime.store.save_depot(_depot(root, f"Depot-{suffix}", suffix=suffix))


def _backup_payload(root: Path, *, suffix: str) -> dict:
    return {
        "format": "omedia-config-backup",
        "version": 2,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "organize": {
            "extensions": {"video": [".mkv", ".mp4"], "subtitle": [".srt"], "sidecar": [".nfo"]},
            "min_non_subtitle_file_size_mb": 75,
        },
        "providers": {
            "tmdb": {
                "api_key": "tmdb-new",
                "base_url": "https://tmdb.example/3",
                "rate_limit": 2.5,
                "proxy": "http://127.0.0.1:10809",
            },
            "llm": {
                "api_key": "llm-new",
                "base_url": "https://llm.restore/v1/",
                "model": "gpt-restore",
                "batch_size": 8,
                "rate_limit": 0.5,
                "proxy": "http://proxy.local:8080",
            },
        },
        "watch_runtime": {"poll_interval_seconds": 7, "stability_debounce_seconds": 19},
        "watch_settings": {"id": "main", "path": str(root / f"watch-{suffix}"), "enabled": False, "metadata": {}},
        "origins": [
            {
                "id": f"origin-{suffix}",
                "name": f"Origin {suffix}",
                "path": str(root / f"origin-{suffix}"),
                "media_type": "movie",
                "trigger": "manual",
                "enabled": True,
                "policy": {"target_depot_id": f"Depot-{suffix}", "organize_rule_id": f"organize-{suffix}"},
                "metadata": {},
            }
        ],
        "depots": [
            {
                "id": f"Depot-{suffix}",
                "name": f"Depot {suffix}",
                "path": str(root / f"Depot-{suffix}"),
                "media_type": "movie",
                "enabled": True,
                "resolve_mode": "full",
                "policy": {
                    "target_library_path": str(root / f"library-{suffix}"),
                    "trigger": "manual",
                    "transfer_rule_id": f"transfer-{suffix}",
                    "schedule": None,
                },
                "metadata": {},
            }
        ],
        "organize_rules": [_rule_payload(f"organize-{suffix}")],
        "transfer_rules": [_rule_payload(f"transfer-{suffix}")],
    }


def _origin(root: Path, suffix: str) -> Origin:
    return Origin(
        id=f"origin-{suffix}",
        name=f"Origin {suffix}",
        path=root / f"origin-{suffix}",
        media_type=MediaType.MOVIE,
        trigger=OriginTrigger.MANUAL,
        policy=OrganizePolicy(target_depot_id=f"Depot-{suffix}", organize_rule_id=f"organize-{suffix}"),
    )


def _depot(root: Path, depot_id: str, *, suffix: str = "a") -> Depot:
    return Depot(
        id=depot_id,
        name=f"Depot {suffix}",
        path=root / f"Depot-{suffix}",
        media_type=MediaType.MOVIE,
        policy=TransferPolicy(target_library_path=root / f"library-{suffix}", trigger=TransferTrigger.MANUAL, transfer_rule_id=f"transfer-{suffix}"),
    )


def _organize_rule(suffix: str) -> OrganizeRule:
    return OrganizeRule(id=f"organize-{suffix}", name=f"Organize {suffix}", categories=[_category()], fallback_bucket="Movies")


def _transfer_rule(suffix: str) -> TransferRule:
    return TransferRule(id=f"transfer-{suffix}", name=f"Transfer {suffix}", categories=[_category()], fallback_bucket="Movies")


def _category() -> RuleCategory:
    return RuleCategory(
        name="Movies",
        bucket="Movies",
        conditions=[RuleCondition(field="relative_path", op=RuleOperator.CONTAINS, value="A")],
    )


def _rule_payload(rule_id: str) -> dict:
    return {
        "id": rule_id,
        "name": rule_id,
        "fallback_bucket": "Movies",
        "description": None,
        "categories": [
            {
                "name": "Movies",
                "bucket": "Movies",
                "conditions": [{"field": "relative_path", "op": "contains", "value": "A"}],
            }
        ],
    }


def _activity(entry_id: str, created_at: datetime) -> ActivityEvent:
    return ActivityEvent(
        id=entry_id,
        time=created_at,
        area=ActivityArea.MANUAL_ORGANIZE,
        entity_type=ActivityEntityType.FILE,
        action=ActivityAction.MOVE_TO_DEPOT,
        status=ActivityStatus.SUCCEEDED,
        entity_source="source.mkv",
        entity_target="dest.mkv",
    )


if __name__ == "__main__":
    unittest.main()
