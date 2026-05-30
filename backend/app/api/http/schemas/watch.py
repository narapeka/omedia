from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.api.http.schemas.common import ApiModel


class WatchSettings(ApiModel):
    id: str = "main"
    path: Path
    enabled: bool = True


class WatchStatus(ApiModel):
    id: str
    label: str
    running: bool
    state: str
    last_event: str | None = None
    last_error: str | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None


class WatchSettingsChild(ApiModel):
    name: str
    path: Path
    status: str
    origin_id: str | None = None
    media_type: str | None = None
    candidate_count: int = 0
    unknown_count: int = 0

