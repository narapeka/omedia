from __future__ import annotations

import unittest

import yaml

from app.domain.media import MediaType
from app.domain.origin import OriginTrigger
from app.domain.transfer import TransferTrigger
from app.domain.origin import OrganizePolicy, Origin
from app.domain.depot import Depot, TransferPolicy
from app.domain.watch import WatchSettings
from app.domain.rule import OrganizeRule, TransferRule
from app.services.config.values import MIB
from support import RuntimeApiFixture, make_common_config


class SettingsApiTests(unittest.TestCase):
    def test_provider_and_organize_settings_are_reported_from_common_config(self) -> None:
        with self._app() as fixture:
            client = fixture.client

            providers = client.get("/api/settings/providers")
            organize_settings = client.get("/api/settings/organize")
            watch_runtime = client.get("/api/settings/watch-runtime")

            self.assertEqual(providers.status_code, 200)
            self.assertEqual(
                providers.json(),
                {
                    "tmdb_api_key": "tmdb-secret",
                    "tmdb_base_url": "https://tmdb.example/3",
                    "tmdb_rate_limit": 2.5,
                    "tmdb_proxy": "http://127.0.0.1:10809",
                    "llm_api_key": "llm-secret",
                    "llm_base_url": "https://llm.example/v1/",
                    "llm_model": "gpt-test",
                    "llm_batch_size": 3,
                    "llm_rate_limit": 0.25,
                    "llm_proxy": "http://127.0.0.1:10810",
                },
            )
            self.assertEqual(organize_settings.status_code, 200)
            self.assertEqual(
                organize_settings.json(),
                {
                    "extensions": {"video": [".mkv"], "subtitle": [".srt"], "sidecar": [".nfo"]},
                    "min_non_subtitle_file_size_mb": 25,
                },
            )
            self.assertEqual(watch_runtime.status_code, 200)
            self.assertEqual(
                watch_runtime.json(),
                {"poll_interval_seconds": 12.0, "stability_debounce_seconds": 34.0},
            )

    def test_saving_organize_settings_updates_yaml_and_live_runtime_services(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            payload = {
                "extensions": {
                    "video": ["mp4", ".MKV"],
                    "subtitle": ["srt"],
                    "sidecar": ["nfo", "jpg"],
                },
                "min_non_subtitle_file_size_mb": 80,
            }
            (root / "watch").mkdir()
            runtime.configuration.save_watch_settings(WatchSettings(path=root / "watch", enabled=True))
            runtime.watch_automation.start()

            response = client.put("/api/settings/organize", json=payload)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["extensions"]["video"], [".mkv", ".mp4"])
            self.assertEqual(response.json()["min_non_subtitle_file_size_mb"], 80)
            data = yaml.safe_load((root / "common.yaml").read_text(encoding="utf-8"))
            self.assertNotIn("media_extensions", data)
            self.assertEqual(data["organize"]["extensions"]["video"], [".mkv", ".mp4"])
            self.assertEqual(data["organize"]["min_non_subtitle_file_size_mb"], 80)
            self.assertEqual(data["tmdb"]["api_key"], "tmdb-secret")
            self.assertEqual(runtime.startup_settings.organize.extensions.video, frozenset({".mkv", ".mp4"}))
            self.assertEqual(runtime.startup_settings.organize.min_non_subtitle_file_size_bytes, 80 * MIB)
            self.assertEqual(runtime.inventory.extensions.video, frozenset({".mkv", ".mp4"}))
            self.assertEqual(runtime.inventory.min_non_subtitle_file_size_bytes, 80 * MIB)
            self.assertEqual(runtime.depot_service.extensions.video, frozenset({".mkv", ".mp4"}))
            self.assertEqual(runtime.transfer_worker.extensions.video, frozenset({".mkv", ".mp4"}))
            self.assertEqual(runtime.organizer.min_non_subtitle_file_size_bytes, 80 * MIB)
            self.assertEqual(runtime.watch_automation.extensions.video, frozenset({".mkv", ".mp4"}))
            self.assertEqual(runtime.watch_automation.min_non_subtitle_file_size_bytes, 80 * MIB)
            self.assertEqual(runtime.watch_automation.worker.min_non_subtitle_file_size_bytes, 80 * MIB)

    def test_saving_provider_settings_updates_yaml_and_live_match_runtime(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            payload = {
                "tmdb_api_key": "tmdb-new",
                "tmdb_base_url": "https://tmdb.new/3",
                "tmdb_rate_limit": 4,
                "tmdb_proxy": None,
                "llm_api_key": "llm-new",
                "llm_base_url": "https://llm.new/v1/",
                "llm_model": "gpt-new",
                "llm_batch_size": 7,
                "llm_rate_limit": 0.5,
                "llm_proxy": None,
            }
            response = client.put("/api/settings/providers", json=payload)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["tmdb_api_key"], "tmdb-new")
            self.assertEqual(response.json()["llm_api_key"], "llm-new")
            data = yaml.safe_load((root / "common.yaml").read_text(encoding="utf-8"))
            self.assertEqual(data["tmdb"]["api_key"], "tmdb-new")
            self.assertEqual(data["llm"]["api_key"], "llm-new")
            self.assertEqual(runtime.startup_settings.providers.tmdb_api_key, "tmdb-new")
            self.assertEqual(runtime.match.settings.providers.llm_api_key, "llm-new")

    def test_saving_provider_settings_rejects_blank_api_key(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            payload = {
                "tmdb_api_key": "",
                "tmdb_base_url": "https://tmdb.example/3",
                "tmdb_rate_limit": 2.5,
                "tmdb_proxy": None,
                "llm_api_key": "llm-new",
                "llm_base_url": "https://llm.example/v1/",
                "llm_model": "gpt-test",
                "llm_batch_size": 3,
                "llm_rate_limit": 0.25,
                "llm_proxy": None,
            }
            response = client.put("/api/settings/providers", json=payload)

            self.assertEqual(response.status_code, 400)
            error = response.json()["error"]
            self.assertEqual(error["code"], "provider.tmdb_required")
            self.assertEqual(error["details"], {"provider": "tmdb"})
            data = yaml.safe_load((root / "common.yaml").read_text(encoding="utf-8"))
            self.assertEqual(data["tmdb"]["api_key"], "tmdb-secret")
            self.assertEqual(runtime.startup_settings.providers.tmdb_api_key, "tmdb-secret")

    def test_saving_watch_runtime_updates_yaml_and_live_watch_service(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client
            payload = {
                "poll_interval_seconds": 8,
                "stability_debounce_seconds": 21,
            }
            (root / "watch").mkdir()
            runtime.configuration.save_watch_settings(WatchSettings(path=root / "watch", enabled=True))
            runtime.watch_automation.start()
            response = client.put("/api/settings/watch-runtime", json=payload)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"poll_interval_seconds": 8.0, "stability_debounce_seconds": 21.0})
            data = yaml.safe_load((root / "common.yaml").read_text(encoding="utf-8"))
            self.assertEqual(data["watch"], {"poll_interval_seconds": 8.0, "stability_debounce_seconds": 21.0})
            self.assertEqual(runtime.startup_settings.watch.poll_interval_seconds, 8.0)
            self.assertEqual(runtime.startup_settings.watch.stability_debounce_seconds, 21.0)
            self.assertEqual(runtime.watch_automation.poll_interval_seconds, 8.0)
            self.assertEqual(runtime.watch_automation.debounce_seconds, 21.0)
            self.assertEqual(runtime.watch_automation.worker.debounce_seconds, 21.0)

    def test_health_reports_lightweight_configuration_counts(self) -> None:
        with self._app() as fixture:
            root = fixture.root
            runtime = fixture.runtime
            client = fixture.client

            watch_root = root / "watch"
            watch_root.mkdir()
            manual_origin = root / "manual-origin"
            manual_origin.mkdir()
            watch_origin = watch_root / "watch-origin"
            watch_origin.mkdir()
            manual_depot = root / "manual-Depot"
            manual_depot.mkdir()
            scheduled_depot = root / "scheduled-Depot"
            scheduled_depot.mkdir()
            runtime.configuration.save_watch_settings(WatchSettings(path=watch_root, enabled=True))
            runtime.configuration.save_depot(
                Depot(
                    id="manual-Depot",
                    name="Manual Depot",
                    path=manual_depot,
                    media_type=MediaType.MOVIE,
                    policy=TransferPolicy(target_library_path=root / "manual-library"),
                )
            )
            runtime.configuration.save_depot(
                Depot(
                    id="scheduled-Depot",
                    name="Scheduled Depot",
                    path=scheduled_depot,
                    media_type=MediaType.TV,
                    policy=TransferPolicy(
                        target_library_path=root / "scheduled-library",
                        trigger=TransferTrigger.SCHEDULED,
                        schedule="0 1 * * *",
                    ),
                )
            )
            runtime.configuration.save_origin(
                Origin(
                    id="manual-origin",
                    name="Manual Origin",
                    path=manual_origin,
                    media_type=MediaType.MOVIE,
                    trigger=OriginTrigger.MANUAL,
                    policy=OrganizePolicy(target_depot_id="manual-Depot"),
                )
            )
            runtime.configuration.save_origin(
                Origin(
                    id="watch-origin",
                    name="Watch Origin",
                    path=watch_origin,
                    media_type=MediaType.TV,
                    trigger=OriginTrigger.WATCH,
                    policy=OrganizePolicy(target_depot_id="scheduled-Depot"),
                )
            )
            runtime.rules.save_organize(OrganizeRule(id="organize-rule", name="Organize"))
            runtime.rules.save_transfer(TransferRule(id="transfer-rule", name="Transfer"))

            response = client.get("/api/settings/health")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                {
                    key: response.json()[key]
                    for key in ("origins", "depots", "organize_rules", "transfer_rules", "watched_folders", "scheduled_transfers")
                },
                {
                    "origins": 1,
                    "depots": 2,
                    "organize_rules": 1,
                    "transfer_rules": 1,
                    "watched_folders": 1,
                    "scheduled_transfers": 1,
                },
            )

    def test_health_reports_database_failure_without_crashing(self) -> None:
        with self._app() as fixture:
            runtime = fixture.runtime
            client = fixture.client

            def fail_ping():
                raise RuntimeError("database unavailable")

            runtime.store.ping = fail_ping

            response = client.get("/api/settings/health")

            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["ok"])
            self.assertFalse(response.json()["database"])
            self.assertTrue(response.json()["config_loaded"])

    def _app(self):
        return RuntimeApiFixture(
            common=make_common_config(
                min_non_subtitle_file_size_mb=25,
                tmdb={
                    "api_key": "tmdb-secret",
                    "base_url": "https://tmdb.example/3",
                    "rate_limit": 2.5,
                    "proxy": "http://127.0.0.1:10809",
                },
                llm={
                    "api_key": "llm-secret",
                    "base_url": "https://llm.example/v1/",
                    "model": "gpt-test",
                    "batch_size": 3,
                    "rate_limit": 0.25,
                    "proxy": "http://127.0.0.1:10810",
                },
                watch={
                    "poll_interval_seconds": 12,
                    "stability_debounce_seconds": 34,
                },
            )
        )


if __name__ == "__main__":
    unittest.main()
