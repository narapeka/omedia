from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from app.core.path import display_sort_key, natural_sort_key
from app.domain.depot import Depot
from app.domain.match import ConfidenceLevel
from app.domain.media import MediaCandidate, MediaExtensionPolicy, MediaFile, MediaType
from app.domain.organize import (
    CandidateDecision,
    CandidatePreview,
    OrganizePlanItem,
    SourceCandidateKind,
    SourceFileClassification,
    SourceFilePlanStatus,
    source_file_id,
)
from app.engines.plan.movie.evidence import movie_plan_ignored_duplicate_subtitles, movie_plan_media_kind
from app.engines.plan.tv.evidence import tv_episode_plan_ignored_duplicate_subtitles, tv_episode_plan_media_kind
from app.services.identify.candidate import CandidateMatch
from app.services.identify.evidence import match_evidence_view_payload
from app.services.organize.session import (
    OrganizeSession,
    OrganizeSessionError,
    SourceCandidateState,
    SourceCandidateStatus,
    SourceFileState,
    SourceFileStatus,
)

if TYPE_CHECKING:
    from app.services.organize.review import ConflictReviewRead, ReviewAcceptance


@dataclass(frozen=True)
class CandidateMatchRead:
    source_candidate_id: str
    confidence: ConfidenceLevel
    metadata: dict[str, Any] | None
    metadata_source: str | None
    manual_override_tmdb_id: str | None
    evidence: dict[str, Any]
    acceptance: "ReviewAcceptance"


@dataclass(frozen=True)
class OrganizePlanItemRead:
    id: str
    source_candidate_id: str
    source_file_id: str
    source_path: Path
    source_size: int | None
    source_mtime: float | None
    confidence: ConfidenceLevel
    metadata: dict[str, Any] | None
    metadata_source: str | None
    manual_override_tmdb_id: str | None
    evidence: dict[str, Any]
    preview: CandidatePreview
    user_decision: CandidateDecision | None
    acceptance: "ReviewAcceptance"


@dataclass(frozen=True)
class SourceFileRead:
    id: str
    path: Path
    relative_path: Path
    extension: str
    classification: SourceFileClassification
    status: SourceFileStatus
    size_bytes: int | None
    modified_time: float | None
    planned_item_ids: list[str]
    plan_status: SourceFilePlanStatus


@dataclass(frozen=True)
class SourceReviewCandidateRead:
    id: str
    media_type: MediaType
    source_root: Path
    source_path: Path
    display_name: str
    structure: str | None
    kind: SourceCandidateKind
    status: SourceCandidateStatus
    selection_decision: CandidateDecision
    file_count: int
    active_file_count: int
    total_size: int | None
    active_total_size: int | None
    modified_time: float | None
    files: list[SourceFileRead]
    match: CandidateMatchRead | None
    plan_items: list[OrganizePlanItemRead]
    conflict_reviews: list["ConflictReviewRead"]
    warnings: list[str]


def source_state(task: OrganizeSession, source_candidate_id: str) -> SourceCandidateState:
    return task.source_states.setdefault(source_candidate_id, SourceCandidateState())


def file_state(task: OrganizeSession, source_candidate_id: str, file: MediaFile) -> SourceFileState:
    return task.file_states.setdefault(source_file_id(source_candidate_id, file.relative_path), SourceFileState())


def find_media_candidate(task: OrganizeSession, source_candidate_id: str | None) -> MediaCandidate:
    for candidate in task.media_candidates:
        if candidate.id == source_candidate_id:
            return candidate
    raise OrganizeSessionError(
        f"Unknown source candidate: {source_candidate_id}",
        code="source_candidate.unknown",
        details={"session_id": task.id, "source_candidate_id": source_candidate_id},
    )


def require_active_candidate(task: OrganizeSession, source_candidate_id: str) -> MediaCandidate:
    candidate = find_media_candidate(task, source_candidate_id)
    state = source_state(task, source_candidate_id)
    if state.status != SourceCandidateStatus.ACTIVE:
        raise OrganizeSessionError(
            f"Source candidate is {state.status.value}: {source_candidate_id}",
            code="source_candidate.inactive",
            details={"session_id": task.id, "source_candidate_id": source_candidate_id, "status": state.status.value},
        )
    return candidate


def find_source_file(task: OrganizeSession, source_candidate_id: str, file_id: str) -> tuple[MediaCandidate, MediaFile]:
    candidate = find_media_candidate(task, source_candidate_id)
    for file in candidate.files:
        if source_file_id(candidate.id, file.relative_path) == file_id:
            return candidate, file
    raise OrganizeSessionError(
        f"Unknown source file: {file_id}",
        code="source_file.unknown",
        details={"session_id": task.id, "source_candidate_id": source_candidate_id, "source_file_id": file_id},
    )


def find_plan_item(task: OrganizeSession, plan_item_id: str) -> OrganizePlanItem:
    for item in task.plan_items:
        if item.id == plan_item_id:
            return item
    raise OrganizeSessionError(
        f"Unknown plan item: {plan_item_id}",
        code="plan_item.unknown",
        details={"session_id": task.id, "plan_item_id": plan_item_id},
    )


def selected_source_candidate_ids(task: OrganizeSession) -> set[str]:
    return {
        candidate.id
        for candidate in task.media_candidates
        if source_state(task, candidate.id).selection_decision == CandidateDecision.ACCEPT
    }


def retain_source_candidates(task: OrganizeSession, source_candidate_ids: set[str]) -> None:
    task.media_candidates = [
        candidate
        for candidate in task.media_candidates
        if candidate.id in source_candidate_ids
    ]
    task.source_states = {
        candidate_id: state
        for candidate_id, state in task.source_states.items()
        if candidate_id in source_candidate_ids
    }
    retained_file_ids = {
        source_file_id(candidate.id, file.relative_path)
        for candidate in task.media_candidates
        for file in candidate.files
    }
    task.file_states = {
        file_id: state
        for file_id, state in task.file_states.items()
        if file_id in retained_file_ids
    }


def source_candidate_kind(candidate: MediaCandidate) -> SourceCandidateKind:
    if candidate.media_type == MediaType.TV:
        return SourceCandidateKind.TV_SHOW
    if candidate.structure == "movie_folder" or candidate.candidate_path.is_dir():
        return SourceCandidateKind.MOVIE_FOLDER
    return SourceCandidateKind.MOVIE_FILE


def sum_optional(values) -> int | None:
    known = [value for value in values if value is not None]
    if not known:
        return None
    return int(sum(known))


def classify_source_file(
    file: MediaFile,
    state: SourceFileState | None,
    extensions: MediaExtensionPolicy,
) -> SourceFileClassification:
    status = state.status if state else SourceFileStatus.ACTIVE
    if status == SourceFileStatus.DELETED:
        return SourceFileClassification.DELETED
    if status == SourceFileStatus.MISSING:
        return SourceFileClassification.MISSING
    if status == SourceFileStatus.BLOCKED:
        return SourceFileClassification.BLOCKED
    extension = file.extension.lower()
    if extension in extensions.video:
        return SourceFileClassification.VIDEO
    if extension in extensions.subtitle:
        return SourceFileClassification.SUBTITLE
    if extension in extensions.sidecar:
        return SourceFileClassification.GENERIC_SIDECAR
    return SourceFileClassification.UNSUPPORTED


def source_review_candidates(
    session: OrganizeSession,
    *,
    extensions: MediaExtensionPolicy,
    target_depot: Depot | None = None,
) -> list[SourceReviewCandidateRead]:
    return [
        _source_review_candidate(session, candidate, extensions=extensions, target_depot=target_depot)
        for candidate in sorted(session.media_candidates, key=_source_candidate_read_sort_key)
    ]


def _source_candidate_read_sort_key(candidate: MediaCandidate):
    return (
        display_sort_key(candidate.display_name),
        natural_sort_key(candidate.candidate_path.as_posix()),
        candidate.id,
    )


def _source_review_candidate(
    session: OrganizeSession,
    candidate: MediaCandidate,
    *,
    extensions: MediaExtensionPolicy,
    target_depot: Depot | None,
) -> SourceReviewCandidateRead:
    from app.services.organize.review import conflict_review_reads

    source_candidate = session.source_states.get(candidate.id)
    source_status = source_candidate.status if source_candidate else SourceCandidateStatus.ACTIVE
    selection_decision = source_candidate.selection_decision if source_candidate else CandidateDecision.ACCEPT
    candidate_plan_items = [
        item
        for item in session.plan_items
        if item.source_candidate_id == candidate.id
    ]
    files = [
        _source_file(
            session,
            candidate,
            file,
            candidate_plan_items,
            extensions=extensions,
        )
        for file in sorted(candidate.files, key=lambda item: item.relative_path.as_posix().lower())
    ]
    active_files = [file for file in files if file.status == SourceFileStatus.ACTIVE]
    warnings: list[str] = []
    if source_status != SourceCandidateStatus.ACTIVE:
        warnings.append(f"source_candidate_{source_status.value}")
    if source_candidate and source_candidate.blocked_reason:
        warnings.append(source_candidate.blocked_reason)
    return SourceReviewCandidateRead(
        id=candidate.id,
        media_type=candidate.media_type,
        source_root=candidate.source_root,
        source_path=candidate.candidate_path,
        display_name=candidate.display_name,
        structure=candidate.structure,
        kind=source_candidate_kind(candidate),
        status=source_status,
        selection_decision=selection_decision,
        file_count=len(files),
        active_file_count=len(active_files),
        total_size=sum_optional(file.size_bytes for file in files),
        active_total_size=sum_optional(file.size_bytes for file in active_files),
        modified_time=_max_optional(file.modified_time for file in active_files),
        files=files,
        match=_candidate_match_for_session(session, session.candidate_matches.get(candidate.id)),
        plan_items=[_plan_item(session, item) for item in _sort_plan_items_for_read(candidate_plan_items)],
        conflict_reviews=conflict_review_reads(session, candidate_plan_items, target_depot=target_depot),
        warnings=warnings,
    )


def _source_file(
    session: OrganizeSession,
    candidate: MediaCandidate,
    file: MediaFile,
    candidate_plan_items: list[OrganizePlanItem],
    *,
    extensions: MediaExtensionPolicy,
) -> SourceFileRead:
    file_id = source_file_id(candidate.id, file.relative_path)
    state = session.file_states.get(file_id)
    status = state.status if state else SourceFileStatus.ACTIVE
    classification = classify_source_file(file, state, extensions=extensions)
    planned_items = [item for item in candidate_plan_items if item.source_file_id == file_id]
    ignored_duplicate_files = _ignored_duplicate_paths(candidate_plan_items)
    return SourceFileRead(
        id=file_id,
        path=file.path,
        relative_path=file.relative_path,
        extension=file.extension,
        classification=classification,
        status=status,
        size_bytes=file.size_bytes,
        modified_time=file.modified_time,
        planned_item_ids=[item.id for item in planned_items],
        plan_status=_source_file_plan_status(file, classification, status, planned_items, ignored_duplicate_files),
    )


def _source_file_plan_status(
    file: MediaFile,
    classification: SourceFileClassification,
    status: SourceFileStatus,
    planned_items: list[OrganizePlanItem],
    ignored_duplicate_files: set[str],
) -> SourceFilePlanStatus:
    if status == SourceFileStatus.DELETED:
        return SourceFilePlanStatus.DELETED
    if status == SourceFileStatus.MISSING:
        return SourceFilePlanStatus.MISSING
    if status == SourceFileStatus.BLOCKED:
        return SourceFilePlanStatus.BLOCKED
    if planned_items:
        media_kinds = {_planned_media_kind(item) for item in planned_items}
        if "primary" in media_kinds:
            return SourceFilePlanStatus.PLANNED_PRIMARY
        if "video" in media_kinds:
            return SourceFilePlanStatus.PLANNED_VIDEO
        if "subtitle" in media_kinds:
            return SourceFilePlanStatus.PLANNED_SUBTITLE
        return SourceFilePlanStatus.PLANNED_PRIMARY
    if file.relative_path.as_posix() in ignored_duplicate_files:
        return SourceFilePlanStatus.IGNORED_DUPLICATE_SUBTITLE
    if classification == SourceFileClassification.VIDEO:
        return SourceFilePlanStatus.UNPLANNED_EXTRA_VIDEO
    if classification == SourceFileClassification.GENERIC_SIDECAR:
        return SourceFilePlanStatus.GENERIC_SIDECAR_IGNORED
    return SourceFilePlanStatus.UNSUPPORTED


def _planned_media_kind(item: OrganizePlanItem) -> str | None:
    return movie_plan_media_kind(item.evidence) or tv_episode_plan_media_kind(item.evidence)


def _ignored_duplicate_paths(plan_items: list[OrganizePlanItem]) -> set[str]:
    ignored: set[str] = set()
    for item in plan_items:
        ignored.update(movie_plan_ignored_duplicate_subtitles(item.evidence))
        ignored.update(tv_episode_plan_ignored_duplicate_subtitles(item.evidence))
    return ignored


def _candidate_match_for_session(session: OrganizeSession, match: CandidateMatch | None) -> CandidateMatchRead | None:
    from app.services.organize.review import candidate_match_acceptance

    if match is None:
        return None
    acceptance = candidate_match_acceptance(session, match)
    return CandidateMatchRead(
        source_candidate_id=match.source_candidate_id,
        confidence=match.confidence,
        metadata=match.metadata,
        metadata_source=match.metadata_source,
        manual_override_tmdb_id=match.manual_override_tmdb_id,
        evidence=match_evidence_view_payload(match.evidence),
        acceptance=acceptance,
    )


def _plan_item(session: OrganizeSession, item: OrganizePlanItem) -> OrganizePlanItemRead:
    from app.services.organize.review import plan_item_acceptance

    acceptance = plan_item_acceptance(session, item)
    return OrganizePlanItemRead(
        id=item.id,
        source_candidate_id=item.source_candidate_id,
        source_file_id=item.source_file_id,
        source_path=item.source_path,
        source_size=item.source_size,
        source_mtime=item.source_mtime,
        confidence=item.confidence,
        metadata=item.metadata,
        metadata_source=item.metadata_source,
        manual_override_tmdb_id=item.manual_override_tmdb_id,
        evidence=match_evidence_view_payload(item.evidence),
        preview=item.preview,
        user_decision=item.user_decision,
        acceptance=acceptance,
    )


def _sort_plan_items_for_read(items: list[OrganizePlanItem]) -> list[OrganizePlanItem]:
    return sorted(items, key=lambda item: (item.source_path.as_posix().lower(), item.id))


def _max_optional(values) -> float | None:
    known = [value for value in values if value is not None]
    if not known:
        return None
    return max(known)
