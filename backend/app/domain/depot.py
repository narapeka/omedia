from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from app.domain.media import MediaType
from app.domain.transfer import TransferTrigger


class ResolveMode(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"


@dataclass(frozen=True)
class TransferPolicy:
    target_library_path: Path
    trigger: TransferTrigger = TransferTrigger.MANUAL
    transfer_rule_id: str | None = None
    schedule: str | None = None


@dataclass(frozen=True)
class Depot:
    id: str
    name: str
    path: Path
    media_type: MediaType
    policy: TransferPolicy
    enabled: bool = True
    resolve_mode: ResolveMode = ResolveMode.FULL
    metadata: dict[str, Any] = field(default_factory=dict)


def effective_depot_resolve_mode(depot: Depot) -> ResolveMode:
    if depot.media_type == MediaType.MOVIE:
        return ResolveMode.FULL
    return ResolveMode(depot.resolve_mode)


class DepotCandidateKind(str, Enum):
    FILE = "file"
    FOLDER = "folder"


class DepotCandidateAction(str, Enum):
    DETAIL = "detail"
    RENAME = "rename"
    DELETE = "delete"


class DepotCandidateActionScope(str, Enum):
    CANDIDATE = "candidate"
    FILE = "file"


class DepotCandidateActionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    MISSING = "missing"
    CONFLICT = "conflict"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class DepotCandidateFile:
    id: str
    path: Path
    relative_path: Path
    candidate_relative_path: Path
    display_name: str
    size_bytes: int | None = None
    modified_time: float | None = None
    extension: str | None = None
    is_media: bool = False
    blocked_reason: str | None = None


@dataclass(frozen=True)
class DepotCandidateGroup:
    key: str
    organize_prefix: Path
    display_name: str


@dataclass(frozen=True)
class DepotCandidate:
    id: str
    kind: DepotCandidateKind
    path: Path
    relative_path: Path
    display_name: str
    size_bytes: int = 0
    modified_time: float | None = None
    file_count: int = 0
    media_count: int = 0
    group: DepotCandidateGroup | None = None
    media_relative_path: Path | None = None
    path_split_confidence: str | None = None
    files: list[DepotCandidateFile] = field(default_factory=list)
    tree: dict = field(default_factory=dict)
    blocked_reason: str | None = None


@dataclass(frozen=True)
class DepotCandidateActionOutcome:
    action: DepotCandidateAction
    scope: DepotCandidateActionScope
    status: DepotCandidateActionStatus
    depot_id: str
    candidate_id: str
    old_candidate_id: str | None = None
    new_candidate_id: str | None = None
    file_id: str | None = None
    old_file_id: str | None = None
    new_file_id: str | None = None
    old_path: Path | None = None
    new_path: Path | None = None
    affected_file_count: int | None = None
    total_size_bytes: int | None = None
    message: str | None = None
    blocked_reason: str | None = None


def depot_candidate_id(depot_id: str, kind: DepotCandidateKind | str, relative_path: Path | str) -> str:
    kind_text = kind.value if isinstance(kind, DepotCandidateKind) else str(kind)
    return _opaque_id("depot-candidate", depot_id, kind_text, _path_text(relative_path))


def depot_candidate_file_id(depot_id: str, relative_path: Path | str) -> str:
    return _opaque_id("depot-candidate-file", depot_id, _path_text(relative_path))


def depot_candidate_group_key(depot_id: str, organize_prefix: Path | str) -> str:
    return _opaque_id("depot-candidate-group", depot_id, _path_text(organize_prefix))


def _opaque_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256()
    digest.update(prefix.encode("utf-8"))
    for part in parts:
        digest.update(b"\0")
        digest.update(str(part).encode("utf-8", errors="ignore"))
    token = base64.urlsafe_b64encode(digest.digest()[:18]).decode("ascii").rstrip("=")
    return f"{prefix}-{token}"


def _path_text(path: Path | str) -> str:
    return Path(path).as_posix()
