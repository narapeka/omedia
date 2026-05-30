from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field

from app.api.http.schemas.common import ApiModel
from app.api.http.schemas.inventory import FileDetail
from app.api.http.schemas.transfer import TransferJob, TransferPolicy
from app.domain.depot import (
    DepotCandidateAction,
    DepotCandidateActionScope,
    DepotCandidateActionStatus,
    DepotCandidateKind,
    ResolveMode,
)
from app.domain.media import MediaType


class DepotDraft(ApiModel):
    name: str
    path: Path
    media_type: MediaType
    policy: TransferPolicy
    resolve_mode: ResolveMode = ResolveMode.FULL
    enabled: bool = True


class Depot(DepotDraft):
    id: str


class DepotSummary(Depot):
    pending_count: int = 0
    last_successful_transfer: TransferJob | None = None
    last_failed_transfer: TransferJob | None = None
    recent_transfers: list[TransferJob] = Field(default_factory=list)


class DepotCandidateFile(ApiModel):
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


class DepotCandidateGroup(ApiModel):
    key: str
    organize_prefix: Path
    display_name: str


class DepotCandidate(ApiModel):
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
    files: list[DepotCandidateFile] = Field(default_factory=list)
    tree: dict[str, Any] = Field(default_factory=dict)
    blocked_reason: str | None = None


class DepotDetail(DepotSummary):
    candidates: list[DepotCandidate] = Field(default_factory=list)


class RenameRequest(ApiModel):
    new_name: str


class DepotCandidateActionOutcome(ApiModel):
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


class DepotCandidateDetail(ApiModel):
    candidate: DepotCandidate
    detail: FileDetail


class DepotCandidateFileDetail(ApiModel):
    candidate: DepotCandidate
    file: DepotCandidateFile
    detail: FileDetail


class DepotCandidateMutationResult(ApiModel):
    outcome: DepotCandidateActionOutcome


class ReturnResult(ApiModel):
    activity_events: list[str]


class ReturnRequest(ApiModel):
    relative_paths: list[Path] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)
    destination_root: Path
