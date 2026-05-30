from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.error import ConfigurationError
from app.domain.media import MediaExtensionPolicy
from app.boot.runtime import resolve_runtime_settings
from app.services.config.values import MIB, parse_organize_settings, parse_provider_settings, parse_watch_settings


class RuntimeSettingsTests(unittest.TestCase):
    def test_defaults_resolve_shared_data_folder_from_backend_cwd(self) -> None:
        backend = Path(__file__).resolve().parents[1]
        data = backend.parent / "data"

        settings = resolve_runtime_settings(cwd=backend)

        self.assertEqual(settings.common_path, data / "common.yaml")
        self.assertEqual(settings.db_path, data / "omedia.sqlite3")

    def test_defaults_resolve_shared_data_folder_from_root_cwd(self) -> None:
        root = Path("runtime-root")
        settings = resolve_runtime_settings(cwd=root)

        self.assertEqual(settings.common_path, root / "data" / "common.yaml")
        self.assertEqual(settings.db_path, root / "data" / "omedia.sqlite3")

    def test_db_path_can_be_supplied_by_runtime_composition(self) -> None:
        root = Path("runtime-root")
        settings = resolve_runtime_settings(
            db_path=root / "arg.sqlite3",
            cwd=root,
        )

        self.assertEqual(settings.common_path, root / "data" / "common.yaml")
        self.assertEqual(settings.db_path, root / "arg.sqlite3")

    def test_provider_settings_parse_rate_limits_base_url_and_proxy(self) -> None:
        providers = parse_provider_settings(
            {
                "tmdb": {
                    "api_key": "tmdb-key",
                    "base_url": "https://tmdb.example/3",
                    "rate_limit": "2.5",
                    "proxy": "http://127.0.0.1:10809",
                },
                "llm": {
                    "api_key": "llm-key",
                    "base_url": "https://llm.example/v1/",
                    "batch_size": 4,
                    "rate_limit": 0.25,
                    "proxy": "http://proxy.local:8080",
                },
            }
        )

        self.assertEqual(providers.tmdb_api_key, "tmdb-key")
        self.assertEqual(providers.tmdb_base_url, "https://tmdb.example/3")
        self.assertEqual(providers.tmdb_rate_limit, 2.5)
        self.assertEqual(providers.tmdb_proxy, "http://127.0.0.1:10809")
        self.assertEqual(providers.llm_base_url, "https://llm.example/v1/")
        self.assertEqual(providers.llm_batch_size, 4)
        self.assertEqual(providers.llm_rate_limit, 0.25)
        self.assertEqual(providers.llm_proxy, "http://proxy.local:8080")

    def test_provider_settings_use_defaults_when_optional_values_are_omitted(self) -> None:
        providers = parse_provider_settings({})

        self.assertEqual(providers.tmdb_base_url, "https://api.themoviedb.org/3")
        self.assertEqual(providers.tmdb_rate_limit, 10.0)
        self.assertIsNone(providers.tmdb_proxy)
        self.assertEqual(providers.llm_base_url, "https://api.openai.com/v1/")
        self.assertEqual(providers.llm_rate_limit, 1.0)
        self.assertIsNone(providers.llm_proxy)

    def test_provider_api_keys_do_not_fall_back_to_environment(self) -> None:
        with patch.dict("os.environ", {"TMDB_API_KEY": "env-tmdb", "OPENAI_API_KEY": "env-llm"}):
            providers = parse_provider_settings({})

        self.assertIsNone(providers.tmdb_api_key)
        self.assertIsNone(providers.llm_api_key)

    def test_provider_rate_limit_must_be_positive(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "tmdb.rate_limit"):
            parse_provider_settings({"tmdb": {"rate_limit": 0}})

        with self.assertRaisesRegex(ConfigurationError, "llm.rate_limit"):
            parse_provider_settings({"llm": {"rate_limit": "fast"}})

    def test_provider_proxy_must_be_plain_http_host_port(self) -> None:
        invalid_values = [
            "https://127.0.0.1:10809",
            "http://user:pass@127.0.0.1:10809",
            "http://127.0.0.1",
            "http://127.0.0.1:10809/path",
            "http://127.0.0.1:10809?x=1",
            "http://127.0.0.1:10809#fragment",
        ]
        for proxy in invalid_values:
            with self.subTest(proxy=proxy):
                with self.assertRaisesRegex(ConfigurationError, "tmdb.proxy"):
                    parse_provider_settings({"tmdb": {"proxy": proxy}})

    def test_watch_settings_parse_timing_values(self) -> None:
        watch = parse_watch_settings(
            {
                "watch": {
                    "poll_interval_seconds": "15",
                    "stability_debounce_seconds": 30,
                }
            }
        )

        self.assertEqual(watch.poll_interval_seconds, 15.0)
        self.assertEqual(watch.stability_debounce_seconds, 30.0)

    def test_watch_settings_use_defaults_when_omitted(self) -> None:
        watch = parse_watch_settings({})

        self.assertEqual(watch.poll_interval_seconds, 15.0)
        self.assertEqual(watch.stability_debounce_seconds, 30.0)

    def test_watch_settings_must_be_positive(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "watch.poll_interval_seconds"):
            parse_watch_settings({"watch": {"poll_interval_seconds": 0}})

        with self.assertRaisesRegex(ConfigurationError, "watch.stability_debounce_seconds"):
            parse_watch_settings({"watch": {"stability_debounce_seconds": "soon"}})

    def test_organize_settings_parse_extensions_and_default_to_50_mib(self) -> None:
        organize = parse_organize_settings(_organize_config())

        self.assertEqual(organize.extensions, MediaExtensionPolicy(video=frozenset({".mkv"}), subtitle=frozenset({".srt"}), sidecar=frozenset({".nfo"})))
        self.assertEqual(organize.min_non_subtitle_file_size_bytes, 50 * MIB)
        self.assertEqual(organize.min_non_subtitle_file_size_mb, 50)

    def test_organize_settings_parse_threshold_and_disable_values(self) -> None:
        organize = parse_organize_settings(_organize_config(min_non_subtitle_file_size_mb="25"))

        self.assertEqual(organize.min_non_subtitle_file_size_bytes, 25 * MIB)
        self.assertEqual(organize.min_non_subtitle_file_size_mb, 25)

        self.assertIsNone(
            parse_organize_settings(_organize_config(min_non_subtitle_file_size_mb=0)).min_non_subtitle_file_size_bytes
        )
        self.assertIsNone(
            parse_organize_settings(_organize_config(min_non_subtitle_file_size_mb=None)).min_non_subtitle_file_size_bytes
        )

    def test_organize_settings_require_nested_extensions(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "organize.extensions"):
            parse_organize_settings({"organize": {"min_non_subtitle_file_size_mb": 50}})

        with self.assertRaisesRegex(ConfigurationError, "organize.extensions.video"):
            parse_organize_settings({"organize": {"extensions": {"subtitle": [".srt"], "sidecar": [".nfo"]}}})

    def test_organize_settings_threshold_must_be_non_negative_integer(self) -> None:
        invalid_values = [-1, "2.5", 2.5, True, "soon"]

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ConfigurationError, "organize.min_non_subtitle_file_size_mb"):
                    parse_organize_settings(_organize_config(min_non_subtitle_file_size_mb=value))


def _organize_config(**overrides):
    organize = {
        "extensions": {
            "video": ["mkv"],
            "subtitle": [".srt"],
            "sidecar": ["nfo"],
        }
    }
    organize.update(overrides)
    return {"organize": organize}


if __name__ == "__main__":
    unittest.main()
