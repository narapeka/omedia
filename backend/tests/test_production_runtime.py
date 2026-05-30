from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from fastapi.testclient import TestClient

from app.boot.runtime import create_runtime_context, resolve_runtime_settings
from app.main import create_app
from support import RuntimeApiFixture, make_common_config


class ProductionRuntimeTests(unittest.TestCase):
    def test_runtime_settings_use_omedia_data_dir_for_config_and_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            data_dir = Path(temp) / "state"
            with patch.dict("os.environ", {"OMEDIA_DATA_DIR": str(data_dir)}, clear=False):
                settings = resolve_runtime_settings(cwd=Path("ignored-root"))

            self.assertEqual(settings.common_path, data_dir / "common.yaml")
            self.assertEqual(settings.db_path, data_dir / "omedia.sqlite3")

    def test_runtime_creates_missing_common_config_from_example(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            common_path = root / "data" / "common.yaml"
            runtime = create_runtime_context(common_path=common_path, db_path=root / "data" / "omedia.sqlite3")
            try:
                self.assertTrue(common_path.is_file())
                data = yaml.safe_load(common_path.read_text(encoding="utf-8"))
                self.assertIn("organize", data)
                self.assertIn("tmdb", data)
            finally:
                runtime.close()

    def test_runtime_does_not_replace_existing_common_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            common_path = root / "data" / "common.yaml"
            common_path.parent.mkdir(parents=True)
            common_text = yaml.safe_dump(make_common_config(watch={"poll_interval_seconds": 42}), sort_keys=False)
            common_path.write_text(common_text, encoding="utf-8")

            runtime = create_runtime_context(common_path=common_path, db_path=root / "data" / "omedia.sqlite3")
            try:
                self.assertEqual(common_path.read_text(encoding="utf-8"), common_text)
                self.assertEqual(runtime.startup_settings.watch.poll_interval_seconds, 42)
            finally:
                runtime.close()

    def test_static_frontend_serves_index_assets_and_keeps_api_namespace(self) -> None:
        with RuntimeApiFixture() as fixture, tempfile.TemporaryDirectory() as temp:
            static_dir = Path(temp)
            assets_dir = static_dir / "assets"
            assets_dir.mkdir()
            (static_dir / "index.html").write_text("<div id=\"root\"></div>", encoding="utf-8")
            (assets_dir / "app.js").write_text("console.log('omedia')", encoding="utf-8")
            client = TestClient(create_app(runtime=fixture.runtime, static_dir=static_dir))

            self.assertEqual(client.get("/").status_code, 200)
            self.assertIn("root", client.get("/dashboard").text)
            self.assertIn("omedia", client.get("/assets/app.js").text)
            self.assertTrue(client.get("/api/settings/health").json()["ok"])
            self.assertEqual(client.get("/api/not-found").status_code, 404)


if __name__ == "__main__":
    unittest.main()
