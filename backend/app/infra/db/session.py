from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.infra.db.settings import DatabaseSettings

SessionFactory = sessionmaker[Session]


def create_database_engine(settings: DatabaseSettings) -> Engine:
    connect_args = {}
    if settings.is_sqlite:
        connect_args["check_same_thread"] = False
        if settings.path and settings.path.parent != settings.path:
            settings.path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(settings.url, connect_args=connect_args, future=True)
    if settings.is_sqlite:
        _install_sqlite_pragmas(engine, settings)
    return engine


def create_session_factory(engine: Engine) -> SessionFactory:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: SessionFactory) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ping_database(factory: SessionFactory) -> None:
    with factory() as session:
        session.execute(text("SELECT 1")).scalar_one()


def _install_sqlite_pragmas(engine: Engine, settings: DatabaseSettings) -> None:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={int(settings.sqlite_busy_timeout_ms)}")
            if settings.sqlite_wal and not settings.is_sqlite_memory:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()
