from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal


ActivityGroup = Literal["organize", "transfer", "file_operations", "automation"]
ActivityFocus = Literal["attention", "failed", "unmatched"]


class ActivityArea(str, Enum):
    MANUAL_ORGANIZE = "manual_organize"
    WATCH_ORGANIZE = "watch_organize"
    FILE_MANAGEMENT = "file_management"
    MANUAL_TRANSFER = "manual_transfer"
    SCHEDULED_TRANSFER = "scheduled_transfer"


class ActivityEntityType(str, Enum):
    FILE = "file"
    FOLDER = "folder"
    MEDIA_ITEM = "media_item"
    ORGANIZE_SESSION = "organize_session"
    WATCH_RUN = "watch_run"
    TRANSFER_JOB = "transfer_job"


class ActivityAction(str, Enum):
    IDENTIFY = "identify"
    MOVE_TO_DEPOT = "move_to_depot"
    RETURN = "return"
    TRANSFER = "transfer"
    RENAME = "rename"
    DELETE = "delete"
    CANCEL = "cancel"


class ActivityStatus(str, Enum):
    QUEUED = "queued"
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ActivityEvent:
    id: str
    area: ActivityArea
    entity_type: ActivityEntityType
    action: ActivityAction
    status: ActivityStatus
    time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str | None = None
    summary: str | None = None
    trace_id: str | None = None
    entity_source: str | None = None
    entity_target: str | None = None
    media_type: str | None = None
    tmdb_id: str | None = None
    origin_id: str | None = None
    origin_name: str | None = None
    origin_path: Path | None = None
    depot_id: str | None = None
    depot_name: str | None = None
    depot_path: Path | None = None
    library_path: Path | None = None
    rule_id: str | None = None
    rule_name: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
