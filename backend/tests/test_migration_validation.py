from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.infra.db.bootstrap import CURRENT_REVISION, initialize_database
from app.boot.settings import load_startup_settings

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


class MigrationValidationTests(unittest.TestCase):
    def test_release_baseline_and_example_config_match_current_code(self) -> None:
        migration_path = (
            WORKSPACE_ROOT
            / "backend"
            / "app"
            / "infra"
            / "db"
            / "migrations"
            / "versions"
            / f"{CURRENT_REVISION}.py"
        )
        self.assertTrue(migration_path.exists(), str(migration_path))
        migration_source = migration_path.read_text(encoding="utf-8")
        self.assertIn(f'revision = "{CURRENT_REVISION}"', migration_source)
        self.assertIn("down_revision = None", migration_source)

        example_config = WORKSPACE_ROOT / "data" / "common.example.yaml"
        self.assertTrue(example_config.exists(), str(example_config))
        settings = load_startup_settings(common_path=example_config)
        self.assertIn(".mkv", settings.organize.extensions.video)
        self.assertIsNone(settings.providers.tmdb_api_key)
        self.assertIsNone(settings.providers.llm_api_key)

    def test_initial_baseline_migration_creates_current_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "state.sqlite"
            initialize_database(db_path)
            engine = create_engine(f"sqlite:///{db_path}")
            try:
                inspector = inspect(engine)
                tables = set(inspector.get_table_names())
                self.assertTrue(
                    {
                        "watch_settings",
                        "origins",
                        "depots",
                        "organize_rules",
                        "transfer_rules",
                        "transfer_jobs",
                        "tmdb_detail_cache",
                        "activity_events",
                        "alembic_version",
                    }.issubset(tables)
                )
                self.assertIn("name", {column["name"] for column in inspector.get_columns("origins")})
                self.assertIn("name", {column["name"] for column in inspector.get_columns("depots")})
                self.assertIn("resolve_mode", {column["name"] for column in inspector.get_columns("depots")})
                self.assertIn("metadata_json", {column["name"] for column in inspector.get_columns("transfer_jobs")})
                self.assertIn("entity_source", {column["name"] for column in inspector.get_columns("activity_events")})
                with engine.begin() as connection:
                    version = connection.execute(text("select version_num from alembic_version")).scalar_one()
                self.assertEqual(version, CURRENT_REVISION)
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
