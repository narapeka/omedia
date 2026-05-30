from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    def to_dict(self) -> dict[str, Any]:
        return {column.name: getattr(self, column.name, None) for column in self.__table__.columns}


def dump_json(value: Any) -> str:
    return json.dumps(_to_jsonable(value), ensure_ascii=False, sort_keys=True)


def load_json(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


def format_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(item) for item in value]
    return value
