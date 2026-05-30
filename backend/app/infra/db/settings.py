from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DatabaseSettings:
    url: str
    path: Path | None = None
    sqlite_busy_timeout_ms: int = 5000
    sqlite_wal: bool = True

    @classmethod
    def from_path(cls, path: str | Path) -> "DatabaseSettings":
        resolved = Path(path)
        return cls(url=sqlite_url_for_path(resolved), path=resolved)

    @classmethod
    def from_url(cls, url: str) -> "DatabaseSettings":
        return cls(url=url)

    @property
    def is_sqlite(self) -> bool:
        return self.url.startswith("sqlite:")

    @property
    def is_sqlite_memory(self) -> bool:
        return self.url in {"sqlite://", "sqlite:///:memory:"} or self.url.endswith(":memory:")


def coerce_database_settings(value: str | Path | DatabaseSettings) -> DatabaseSettings:
    if isinstance(value, DatabaseSettings):
        return value
    text = str(value)
    if "://" in text:
        return DatabaseSettings.from_url(text)
    return DatabaseSettings.from_path(value)


def sqlite_url_for_path(path: str | Path) -> str:
    resolved = Path(path)
    return f"sqlite:///{resolved.as_posix()}"
