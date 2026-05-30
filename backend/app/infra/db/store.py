from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.orm import Session

from app.infra.db.bootstrap import migrate_database
from app.infra.db.records.activity import ActivityRecords
from app.infra.db.records.admin import AdminRecords
from app.infra.db.records.config import ConfigRecords
from app.infra.db.records.rule import RuleRecords
from app.infra.db.records.tmdb import TMDBCacheRecords
from app.infra.db.records.transfer import TransferJobRecords
from app.infra.db.session import create_database_engine, create_session_factory, ping_database
from app.infra.db.settings import DatabaseSettings, coerce_database_settings


class Store(
    AdminRecords,
    ConfigRecords,
    RuleRecords,
    TransferJobRecords,
    TMDBCacheRecords,
    ActivityRecords,
):
    def __init__(self, settings_or_path: str | Path | DatabaseSettings):
        self.settings = coerce_database_settings(settings_or_path)
        self.path = self.settings.path
        self.engine = create_database_engine(self.settings)
        self.session_factory = create_session_factory(self.engine)

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def close(self) -> None:
        self.engine.dispose()

    def initialize(self) -> None:
        migrate_database(self.settings, engine=self.engine)

    def ping(self) -> None:
        ping_database(self.session_factory)
