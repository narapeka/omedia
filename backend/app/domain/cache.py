from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class TMDBDetailCache:
    media_type: str
    tmdb_id: int
    metadata: dict[str, Any]
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
