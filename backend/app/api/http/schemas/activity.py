from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import Field

from app.api.http.schemas.common import ApiModel
from app.domain.activity import ActivityAction, ActivityArea, ActivityEntityType, ActivityStatus


class ActivityEvent(ApiModel):
    id: str
    time: datetime
    area: ActivityArea
    entity_type: ActivityEntityType
    action: ActivityAction
    status: ActivityStatus
    reason: str | None = None
    summary: str | None = None
    entity_source: str | None = None
    entity_target: str | None = None
    origin_id: str | None = None
    origin_name: str | None = None
    origin_path: Path | None = None
    depot_id: str | None = None
    depot_name: str | None = None
    depot_path: Path | None = None
    rule_id: str | None = None
    rule_name: str | None = None
    library_path: Path | None = None
    media_type: str | None = None
    tmdb_id: str | None = None
    trace_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class ActivityEventList(ApiModel):
    items: list[ActivityEvent]
    limit: int
    offset: int
    has_more: bool = False
