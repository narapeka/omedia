from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from app.domain.media import MediaType

UNKNOWN_FOLDER_NAME = ".unknown"


class OriginTrigger(str, Enum):
    MANUAL = "manual"
    WATCH = "watch"


@dataclass(frozen=True)
class OrganizePolicy:
    target_depot_id: str
    organize_rule_id: str | None = None


@dataclass(frozen=True)
class Origin:
    id: str
    name: str
    path: Path
    media_type: MediaType
    trigger: OriginTrigger
    policy: OrganizePolicy
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
