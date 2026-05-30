from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import base64
import hashlib
from pathlib import Path
from typing import Any

from app.domain.match import ConfidenceLevel


class OrganizeSessionKind(str, Enum):
    ORIGIN = "origin"
    AD_HOC = "ad_hoc"


class OrganizeSessionState(str, Enum):
    SCANNING = "scanning"
    SCANNED = "scanned"
    IDENTIFYING = "identifying"
    IDENTIFIED = "identified"
    ORGANIZING = "organizing"
    DONE = "done"
    CANCELLED = "cancelled"


class CandidateDecision(str, Enum):
    ACCEPT = "accept"
    IGNORE = "ignore"


class ConflictReviewAction(str, Enum):
    KEEP = "keep"
    KEEP_AND_REPLACE = "keep_and_replace"
    REPLACE_TARGET = "replace_target"
    TAG_VARIANT = "tag_variant"


class ConflictReviewStatus(str, Enum):
    READY = "ready"
    TARGET_EXISTS = "target_exists"
    DUPLICATE_SOURCE = "duplicate_source"
    DUPLICATE_SOURCE_AND_TARGET_EXISTS = "duplicate_source_and_target_exists"


class BulkSessionItemStatus(str, Enum):
    CREATED = "created"
    DUPLICATE = "duplicate"
    WATCH_ORIGIN = "watch_origin"
    DISABLED = "disabled"
    CONFLICT = "conflict"
    MISSING = "missing"
    INVALID = "invalid"


class SourceCandidateKind(str, Enum):
    MOVIE_FILE = "movie_file"
    MOVIE_FOLDER = "movie_folder"
    TV_SHOW = "tv_show"


class SourceFileClassification(str, Enum):
    VIDEO = "video"
    SUBTITLE = "subtitle"
    GENERIC_SIDECAR = "generic_sidecar"
    UNSUPPORTED = "unsupported"
    DELETED = "deleted"
    MISSING = "missing"
    BLOCKED = "blocked"


class SourceCandidateStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"


class SourceFileStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"
    MISSING = "missing"
    BLOCKED = "blocked"


class SourceFilePlanStatus(str, Enum):
    PLANNED_PRIMARY = "planned_primary"
    PLANNED_VIDEO = "planned_video"
    PLANNED_SUBTITLE = "planned_subtitle"
    IGNORED_DUPLICATE_SUBTITLE = "ignored_duplicate_subtitle"
    UNPLANNED_EXTRA_VIDEO = "unplanned_extra_video"
    GENERIC_SIDECAR_IGNORED = "generic_sidecar_ignored"
    UNSUPPORTED = "unsupported"
    DELETED = "deleted"
    MISSING = "missing"
    BLOCKED = "blocked"


class SourceActionOperation(str, Enum):
    RENAME = "rename"
    DELETE = "delete"


class SourceActionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    MISSING = "missing"
    CONFLICT = "conflict"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass
class CandidatePreview:
    preview_bucket: str | None = None
    matched_category: str | None = None
    proposed_relative_path: Path | None = None
    render_warnings: list[str] = field(default_factory=list)


@dataclass
class OrganizePlanItem:
    id: str
    source_path: Path
    confidence: ConfidenceLevel
    source_candidate_id: str | None = None
    source_file_id: str | None = None
    source_size: int | None = None
    source_mtime: float | None = None
    metadata: dict[str, Any] | None = None
    metadata_source: str | None = None
    manual_override_tmdb_id: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    preview: CandidatePreview = field(default_factory=CandidatePreview)
    user_decision: CandidateDecision | None = None

    def __post_init__(self) -> None:
        if self.source_candidate_id is None:
            self.source_candidate_id = self.id
        if self.source_file_id is None:
            self.source_file_id = self.id


def source_file_id(source_candidate_id: str, relative_path: Path | str) -> str:
    relative = relative_path.as_posix() if isinstance(relative_path, Path) else str(relative_path).replace("\\", "/")
    return "file_" + _opaque_id(f"{source_candidate_id}\n{relative.casefold()}")


def plan_item_id(source_candidate_id: str, relative_path: Path | str) -> str:
    relative = relative_path.as_posix() if isinstance(relative_path, Path) else str(relative_path).replace("\\", "/")
    return "plan_" + _opaque_id(f"{source_candidate_id}\n{relative.casefold()}")


def _opaque_id(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8", errors="ignore")).digest()
    return base64.urlsafe_b64encode(digest[:18]).decode("ascii").rstrip("=")
