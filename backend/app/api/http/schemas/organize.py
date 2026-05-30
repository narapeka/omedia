from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import Field

from app.api.http.schemas.common import ApiModel
from app.api.http.schemas.config import OrganizePolicy
from app.api.http.schemas.inventory import FileDetail
from app.domain.match import ConfidenceLevel
from app.domain.media import MediaType
from app.domain.result import ResultStatus
from app.domain.organize import (
    BulkSessionItemStatus,
    CandidateDecision,
    ConflictReviewAction,
    ConflictReviewStatus,
    OrganizeSessionKind,
    OrganizeSessionState,
    SourceActionOperation,
    SourceActionStatus,
    SourceCandidateKind,
    SourceCandidateStatus,
    SourceFileClassification,
    SourceFilePlanStatus,
    SourceFileStatus,
)


class OrganizeRequest(ApiModel):
    origin_id: str | None = None
    source_path: Path | None = None
    media_type: MediaType | None = None
    policy: OrganizePolicy | None = None


class OrganizeBulkSessionCreateRequest(ApiModel):
    origin_ids: list[str]


class BulkSessionItemResult(ApiModel):
    origin_id: str
    status: BulkSessionItemStatus
    session_id: str | None = None
    message: str | None = None
    code: str | None = None
    details: dict[str, Any] | None = None


class RenameRequest(ApiModel):
    new_name: str


class CandidatePreview(ApiModel):
    preview_bucket: str | None = None
    matched_category: str | None = None
    proposed_relative_path: Path | None = None
    render_warnings: list[str]


class ReviewAcceptance(ApiModel):
    can_accept: bool
    blockers: list[str]


class CandidateMatch(ApiModel):
    source_candidate_id: str
    confidence: ConfidenceLevel
    metadata: dict[str, Any] | None = None
    metadata_source: str | None = None
    manual_override_tmdb_id: str | None = None
    evidence: dict[str, Any]
    acceptance: ReviewAcceptance


class PlanItem(ApiModel):
    id: str
    source_candidate_id: str
    source_file_id: str
    source_path: Path
    source_size: int | None = None
    source_mtime: float | None = None
    confidence: ConfidenceLevel
    metadata: dict[str, Any] | None = None
    metadata_source: str | None = None
    manual_override_tmdb_id: str | None = None
    evidence: dict[str, Any]
    preview: CandidatePreview
    user_decision: CandidateDecision | None = None
    acceptance: ReviewAcceptance


class ConflictReview(ApiModel):
    identity_key: str
    kind: str
    status: ConflictReviewStatus = ConflictReviewStatus.READY
    display_path: Path
    root_relative_path: Path
    plan_item_ids: list[str]
    source_candidate_ids: list[str]
    accepted_source_candidate_ids: list[str] = Field(default_factory=list)
    action_required: bool = False
    conflict: bool = False
    conflict_reason: str | None = None
    existing: bool = False
    action: ConflictReviewAction | None = None
    action_source_candidate_id: str | None = None
    replace_intent: bool = False
    source_tag: str | None = None


class ConflictReviewActionRequest(ApiModel):
    identity_key: str
    source_candidate_id: str
    action: ConflictReviewAction
    tag_override: str | None = None


class SourceFile(ApiModel):
    id: str
    path: Path
    relative_path: Path
    extension: str
    classification: SourceFileClassification
    status: SourceFileStatus
    size_bytes: int | None = None
    modified_time: float | None = None
    planned_item_ids: list[str]
    plan_status: SourceFilePlanStatus


class SourceCandidate(ApiModel):
    id: str
    media_type: MediaType
    source_root: Path
    source_path: Path
    display_name: str
    structure: str | None = None
    kind: SourceCandidateKind
    status: SourceCandidateStatus
    selection_decision: CandidateDecision
    file_count: int
    active_file_count: int
    total_size: int | None = None
    active_total_size: int | None = None
    modified_time: float | None = None
    files: list[SourceFile]
    match: CandidateMatch | None = None
    plan_items: list[PlanItem]
    conflict_reviews: list[ConflictReview] = Field(default_factory=list)
    warnings: list[str]


class SourceActionOutcome(ApiModel):
    operation: SourceActionOperation
    status: SourceActionStatus
    scope: str
    source_candidate_id: str
    source_file_id: str | None = None
    old_source_file_id: str | None = None
    new_source_file_id: str | None = None
    message: str
    file_count: int
    total_size: int
    old_path: Path | None = None
    new_path: Path | None = None
    exists_after: bool | None = None
    exists_after_old: bool | None = None
    exists_after_new: bool | None = None
    blocked_reason: str | None = None


class OrganizeSession(ApiModel):
    id: str
    kind: OrganizeSessionKind
    path: Path
    media_type: MediaType
    policy: OrganizePolicy
    state: OrganizeSessionState
    created_at: datetime
    last_active_at: datetime
    expires_at: datetime
    idle_timeout_seconds: int
    review_candidates: list[SourceCandidate]
    last_source_action_outcome: SourceActionOutcome | None = None


class OrganizeBulkSessionCreateResult(ApiModel):
    sessions: list[OrganizeSession]
    results: list[BulkSessionItemResult]


class SourceFileDetail(ApiModel):
    entry_kind: str = "file"
    path: Path
    exists: bool
    file_type: str
    size_bytes: int | None = None
    created_time: float | None = None
    modified_time: float | None = None
    classification: SourceFileClassification
    source_candidate_id: str
    source_candidate_display_name: str
    source_candidate_kind: SourceCandidateKind | None = None
    source_candidate_status: SourceCandidateStatus | None = None
    source_candidate_path: Path | None = None
    source_root: Path | None = None
    file_count: int | None = None
    total_size: int | None = None
    source_file_id: str
    relative_path: Path
    blocked_reason: str | None = None


class SourceCandidateDetail(ApiModel):
    candidate: SourceCandidate
    detail: FileDetail


class CandidateDecisionRequest(ApiModel):
    decision: CandidateDecision


class IdentityOverrideRequest(ApiModel):
    tmdb_id: int


class IdentifySearchRequest(ApiModel):
    source_candidate_id: str | None = None
    query: str | None = None
    year: int | None = None
    language: str | None = None
    page: int = 1


class IdentifySearchResult(ApiModel):
    tmdb_id: int
    media_type: MediaType
    title: str
    original_title: str | None = None
    year: int | None = None
    overview: str | None = None
    poster_url: str | None = None
    vote_average: float | None = None
    popularity: float | None = None
    origin_country: list[str] = Field(default_factory=list)
    directors: list[str] = Field(default_factory=list)
    cast: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel
    score: int
    reason: str


class IdentifySearchResults(ApiModel):
    results: list[IdentifySearchResult]
    page: int
    total_pages: int
    total_results: int


class PlanItemResult(ApiModel):
    plan_item_id: str
    source_candidate_id: str | None = None
    status: ResultStatus
    source_path: Path
    destination_path: Path | None = None
    message: str | None = None


class OrganizeResult(ApiModel):
    session_id: str
    moved: int
    skipped: int
    failed: int
    results: list[PlanItemResult]
