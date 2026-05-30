from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine

from app.infra.db.settings import DatabaseSettings, coerce_database_settings
from app.infra.db.session import create_database_engine

CURRENT_REVISION = "0001_initial_schema"


def initialize_database(settings_or_path: str | Path | DatabaseSettings) -> None:
    settings = coerce_database_settings(settings_or_path)
    engine = create_database_engine(settings)
    try:
        migrate_database(settings, engine=engine)
    finally:
        engine.dispose()


def migrate_database(settings: DatabaseSettings, *, engine: Engine | None = None) -> None:
    own_engine = engine is None
    active_engine = engine or create_database_engine(settings)
    try:
        command.upgrade(_alembic_config(settings), "head")
    finally:
        if own_engine:
            active_engine.dispose()


def _alembic_config(settings: DatabaseSettings) -> Config:
    config = Config()
    config.set_main_option("script_location", str(_migration_root()))
    config.set_main_option("sqlalchemy.url", settings.url)
    config.attributes["database_settings"] = settings
    return config


def _migration_root() -> Path:
    return Path(__file__).resolve().parent / "migrations"
