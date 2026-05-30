from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from app.core.error import ConfigurationError, OmediaError
from app.core.path import normalized_path_key
from app.domain.depot import Depot
from app.domain.media import MediaCandidate, MediaExtensionPolicy, MediaType
from app.domain.organize import (
    CandidateDecision,
    ConflictReviewAction,
    BulkSessionItemStatus,
    OrganizePlanItem,
    OrganizeSessionKind,
    OrganizeSessionState,
    SourceCandidateStatus,
    SourceFileStatus,
    source_file_id,
)
from app.domain.origin import Origin
from app.domain.origin import OriginTrigger
from app.domain.origin import OrganizePolicy
from app.domain.watch import WatchSettings
from app.services.identify.candidate import CandidateMatch

if TYPE_CHECKING:
    from app.services.organize.candidate import SourceReviewCandidateRead
    from app.services.organize.source import SourceActionOutcome


@dataclass
class ConflictReviewState:
    action: ConflictReviewAction | None = None
    source_candidate_id: str | None = None
    replace: bool = False
    tag_override: str | None = None


@dataclass
class DeleteMetadata:
    deleted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scope: str | None = None
    reason: str | None = None
    file_count: int | None = None
    total_size: int | None = None


@dataclass
class SourceCandidateState:
    status: SourceCandidateStatus = SourceCandidateStatus.ACTIVE
    selection_decision: CandidateDecision = CandidateDecision.ACCEPT
    delete_metadata: DeleteMetadata | None = None
    blocked_reason: str | None = None


@dataclass
class SourceFileState:
    status: SourceFileStatus = SourceFileStatus.ACTIVE
    delete_metadata: DeleteMetadata | None = None
    blocked_reason: str | None = None


@dataclass
class OrganizeSession:
    id: str
    kind: OrganizeSessionKind
    path: Path
    media_type: MediaType
    policy: OrganizePolicy
    origin_id: str | None = None
    state: OrganizeSessionState = OrganizeSessionState.SCANNING
    media_candidates: list[MediaCandidate] = field(default_factory=list)
    candidate_matches: dict[str, CandidateMatch] = field(default_factory=dict)
    plan_items: list[OrganizePlanItem] = field(default_factory=list)
    source_states: dict[str, SourceCandidateState] = field(default_factory=dict)
    file_states: dict[str, SourceFileState] = field(default_factory=dict)
    conflict_review_states: dict[str, ConflictReviewState] = field(default_factory=dict)
    conflict_tag_overrides: dict[str, str] = field(default_factory=dict)
    last_source_action_outcome: SourceActionOutcome | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def candidates(self) -> list[OrganizePlanItem]:
        return self.plan_items

    @candidates.setter
    def candidates(self, value: list[OrganizePlanItem]) -> None:
        self.plan_items = value


@dataclass(frozen=True)
class OrganizeSessionRead:
    id: str
    kind: object
    path: Path
    media_type: MediaType
    policy: dict[str, str | None]
    state: object
    created_at: datetime
    last_active_at: datetime
    expires_at: datetime
    idle_timeout_seconds: int
    review_candidates: list["SourceReviewCandidateRead"]
    last_source_action_outcome: "SourceActionOutcome | None"


class OrganizeSessionError(OmediaError):
    pass


class OrganizeSessionConflict(OrganizeSessionError):
    pass


ACTIVE_WORK_STATES = frozenset(
    {
        OrganizeSessionState.SCANNING,
        OrganizeSessionState.IDENTIFYING,
        OrganizeSessionState.ORGANIZING,
    }
)


def require_state(task: OrganizeSession, allowed: set[OrganizeSessionState]) -> None:
    if task.state not in allowed:
        allowed_values = ", ".join(sorted(state.value for state in allowed))
        raise OrganizeSessionError(
            f"OrganizeSession {task.id} is {task.state.value}; expected one of: {allowed_values}",
            code="organize.session_state",
            details={"session_id": task.id, "state": task.state.value, "expected": sorted(state.value for state in allowed)},
        )


def validate_ad_hoc_source(
    source_path: Path,
    *,
    watch_settings: WatchSettings | None = None,
    origins: Sequence[Origin] = (),
    depots: Sequence[Depot] = (),
) -> None:
    if not source_path.is_absolute():
        raise ConfigurationError(
            f"Ad hoc source path must be absolute: {source_path}",
            code="path.not_absolute",
            details={"label": "Ad hoc source", "path": str(source_path)},
        )
    if any(part.casefold() == ".unknown" for part in source_path.parts):
        raise ConfigurationError(
            f"Ad hoc source cannot use reserved .unknown path: {source_path}",
            code="path.reserved_unknown",
            details={"label": "Ad hoc source", "path": str(source_path)},
        )
    if not source_path.exists() or not source_path.is_dir():
        raise ConfigurationError(
            f"Ad hoc source must be an existing directory: {source_path}",
            code="path.must_exist_directory",
            details={"label": "Ad hoc source", "path": str(source_path)},
        )
    managed: list[tuple[str, Path]] = []
    if watch_settings is not None:
        managed.append(("WatchSettings", watch_settings.path))
    managed.extend((f"Origin {origin.id}", origin.path) for origin in origins)
    for depot in depots:
        managed.append((f"Depot {depot.id}", depot.path))
        managed.append((f"Depot {depot.id} Library", depot.policy.target_library_path))
    for label, path in managed:
        if _paths_overlap(source_path, path):
            raise ConfigurationError(
                f"Ad hoc source overlaps managed path {label}: {path}",
                code="path.overlap",
                details={"left_label": "Ad hoc source", "left_path": str(source_path), "right_label": label, "right_path": str(path)},
            )


class SessionReads:
    def __init__(self, *, configuration, sessions, settings) -> None:
        self.configuration = configuration
        self.sessions = sessions
        self.settings = settings

    def session(self, session: OrganizeSession) -> OrganizeSessionRead:
        return session_read(
            session,
            configuration=self.configuration,
            sessions=self.sessions,
            extensions=self.settings.organize.extensions,
        )

    def by_id(self, session_id: str) -> OrganizeSessionRead:
        return self.session(self.sessions.get(session_id))

    def source_candidate(self, session_id: str, candidate_id: str) -> "SourceReviewCandidateRead":
        for candidate in self.by_id(session_id).review_candidates:
            if candidate.id == candidate_id:
                return candidate
        raise OmediaError(f"Unknown source candidate: {candidate_id}")


def session_read(
    session: OrganizeSession,
    *,
    configuration,
    sessions,
    extensions: MediaExtensionPolicy,
) -> OrganizeSessionRead:
    from app.services.organize.candidate import source_review_candidates

    try:
        target_depot = _depot_for_ref(configuration, session.policy.target_depot_id)
    except OmediaError:
        target_depot = None
    return OrganizeSessionRead(
        id=session.id,
        kind=session.kind,
        path=session.path,
        media_type=session.media_type,
        policy={
            "target_depot_id": session.policy.target_depot_id,
            "organize_rule_id": session.policy.organize_rule_id,
        },
        state=session.state,
        created_at=session.created_at,
        last_active_at=session.last_active_at,
        expires_at=sessions.expires_at(session),
        idle_timeout_seconds=sessions.idle_timeout_seconds,
        review_candidates=source_review_candidates(
            session,
            extensions=extensions,
            target_depot=target_depot,
        ),
        last_source_action_outcome=session.last_source_action_outcome,
    )


def _paths_overlap(left: Path, right: Path) -> bool:
    left_norm = normalized_path_key(left)
    right_norm = normalized_path_key(right)
    return left_norm == right_norm or left_norm.startswith(f"{right_norm}/") or right_norm.startswith(f"{left_norm}/")


@dataclass(frozen=True)
class BulkSessionItem:
    origin_id: str
    status: BulkSessionItemStatus
    session_id: str | None = None
    message: str | None = None
    code: str | None = None
    details: dict[str, object] | None = None


@dataclass(frozen=True)
class BulkSessionCreateResult:
    sessions: list[OrganizeSession]
    results: list[BulkSessionItem]


class SessionBook:
    def __init__(self, *, idle_timeout_seconds: int = 1800, now=None) -> None:
        self._sessions: dict[str, OrganizeSession] = {}
        self._manual_slots: dict[str, str] = {}
        self._ad_hoc_session_id: str | None = None
        self.idle_timeout_seconds = idle_timeout_seconds
        self.now = now or (lambda: datetime.now(timezone.utc))

    def create_for_origin(self, origin: Origin) -> OrganizeSession:
        self.sweep_stale()
        if origin.trigger == OriginTrigger.WATCH:
            raise ConfigurationError(
                "Watched folders are automatic and cannot create OrganizeSessions",
                code="origin.watch_automatic",
                details={"origin_id": origin.id, "origin_name": origin.name},
            )
        if origin.id in self._manual_slots:
            raise OrganizeSessionConflict(
                f"Manual Origin already has an active OrganizeSession: {origin.id}",
                code="origin.manual_active_session",
                details={"origin_id": origin.id, "origin_name": origin.name, "session_id": self._manual_slots[origin.id]},
            )
        now = self.now()
        task = OrganizeSession(
            id=_session_id(),
            kind=OrganizeSessionKind.ORIGIN,
            path=origin.path,
            media_type=origin.media_type,
            policy=origin.policy,
            origin_id=origin.id,
            state=OrganizeSessionState.SCANNING,
            created_at=now,
            last_active_at=now,
        )
        self._sessions[task.id] = task
        self._manual_slots[origin.id] = task.id
        return task

    def create_ad_hoc(
        self,
        *,
        source_path: Path,
        media_type: MediaType,
        policy: OrganizePolicy,
        watch_settings: WatchSettings | None = None,
        origins: Sequence[Origin] = (),
        depots: Sequence[Depot] = (),
    ) -> OrganizeSession:
        self.sweep_stale()
        if self._ad_hoc_session_id is not None:
            raise OrganizeSessionConflict(
                "An ad hoc OrganizeSession is already active",
                code="organize.ad_hoc_active",
                details={"session_id": self._ad_hoc_session_id},
            )
        validate_ad_hoc_source(source_path, watch_settings=watch_settings, origins=origins, depots=depots)
        now = self.now()
        task = OrganizeSession(
            id=_session_id(),
            kind=OrganizeSessionKind.AD_HOC,
            path=source_path,
            media_type=media_type,
            policy=policy,
            state=OrganizeSessionState.SCANNING,
            created_at=now,
            last_active_at=now,
        )
        self._sessions[task.id] = task
        self._ad_hoc_session_id = task.id
        return task

    def get(self, session_id: str) -> OrganizeSession:
        self.sweep_stale()
        try:
            task = self._sessions[session_id]
        except KeyError as exc:
            raise OrganizeSessionError(
                f"Unknown OrganizeSession: {session_id}",
                code="organize_session.unknown",
                details={"session_id": session_id},
            ) from exc
        self._touch(task)
        return task

    def cancel(self, session_id: str) -> OrganizeSession:
        task = self.get(session_id)
        task.state = OrganizeSessionState.CANCELLED
        self._release_slot(session_id)
        self._sessions.pop(session_id, None)
        return task

    def finish(self, session_id: str) -> OrganizeSession:
        task = self.get(session_id)
        task.state = OrganizeSessionState.DONE
        self._release_slot(session_id)
        self._sessions.pop(session_id, None)
        return task

    def mark_scanned(self, session_id: str, media_candidates: list[MediaCandidate]) -> OrganizeSession:
        task = self.get(session_id)
        require_state(task, {OrganizeSessionState.SCANNING})
        task.media_candidates = sorted(list(media_candidates), key=lambda item: item.display_name.casefold())
        task.candidate_matches = {}
        task.plan_items = []
        task.source_states = {
            candidate.id: SourceCandidateState()
            for candidate in task.media_candidates
        }
        task.file_states = {
            source_file_id(candidate.id, file.relative_path): SourceFileState()
            for candidate in task.media_candidates
            for file in candidate.files
        }
        task.conflict_review_states = {}
        task.conflict_tag_overrides = {}
        task.last_source_action_outcome = None
        task.state = OrganizeSessionState.SCANNED
        return task

    def restart_scan(self, session_id: str) -> OrganizeSession:
        task = self.get(session_id)
        require_state(task, {OrganizeSessionState.SCANNED, OrganizeSessionState.IDENTIFIED})
        task.media_candidates = []
        task.candidate_matches = {}
        task.plan_items = []
        task.source_states = {}
        task.file_states = {}
        task.conflict_review_states = {}
        task.conflict_tag_overrides = {}
        task.last_source_action_outcome = None
        task.state = OrganizeSessionState.SCANNING
        return task

    def start_identify(self, session_id: str) -> OrganizeSession:
        task = self.get(session_id)
        require_state(task, {OrganizeSessionState.SCANNED})
        task.state = OrganizeSessionState.IDENTIFYING
        return task

    def mark_identified(
        self,
        session_id: str,
        *,
        candidate_matches: dict[str, CandidateMatch],
        plan_items: list[OrganizePlanItem],
        selected_source_candidate_ids: set[str] | None = None,
        target_depot: Depot | None = None,
    ) -> OrganizeSession:
        from app.services.organize.candidate import retain_source_candidates
        from app.services.organize.review import (
            apply_conflict_review_defaults,
            apply_existing_tag_overrides,
            auto_accept_high_confidence_plan_items,
            sort_plan_items,
        )

        task = self.get(session_id)
        require_state(task, {OrganizeSessionState.IDENTIFYING})
        if selected_source_candidate_ids is not None:
            retain_source_candidates(task, selected_source_candidate_ids)
        task.candidate_matches = candidate_matches
        task.plan_items = sort_plan_items(plan_items)
        task.conflict_review_states = {}
        auto_accept_high_confidence_plan_items(task)
        apply_existing_tag_overrides(task)
        apply_conflict_review_defaults(task, target_depot=target_depot)
        task.state = OrganizeSessionState.IDENTIFIED
        return task

    def start_organize(self, session_id: str) -> OrganizeSession:
        task = self.get(session_id)
        require_state(task, {OrganizeSessionState.IDENTIFIED})
        task.state = OrganizeSessionState.ORGANIZING
        return task

    def fail_identify(self, session_id: str) -> OrganizeSession:
        task = self.get(session_id)
        require_state(task, {OrganizeSessionState.IDENTIFYING})
        task.state = OrganizeSessionState.SCANNED
        return task

    def fail_organize(self, session_id: str) -> OrganizeSession:
        task = self.get(session_id)
        require_state(task, {OrganizeSessionState.ORGANIZING})
        task.state = OrganizeSessionState.IDENTIFIED
        return task

    def active_sessions(self) -> list[OrganizeSession]:
        self.sweep_stale()
        tasks = list(self._sessions.values())
        for task in tasks:
            self._touch(task)
        return tasks

    def expires_at(self, task: OrganizeSession) -> datetime:
        return task.last_active_at + timedelta(seconds=self.idle_timeout_seconds)

    def sweep_stale(self) -> list[OrganizeSession]:
        cutoff = self.now() - timedelta(seconds=self.idle_timeout_seconds)
        stale = [
            task
            for task in self._sessions.values()
            if task.state not in ACTIVE_WORK_STATES and task.last_active_at < cutoff
        ]
        for task in stale:
            task.state = OrganizeSessionState.CANCELLED
            self._release_slot(task.id)
            self._sessions.pop(task.id, None)
        return stale

    def _touch(self, task: OrganizeSession) -> None:
        task.last_active_at = self.now()

    def _release_slot(self, session_id: str) -> None:
        for origin_id, active_session_id in list(self._manual_slots.items()):
            if active_session_id == session_id:
                self._manual_slots.pop(origin_id, None)
        if self._ad_hoc_session_id == session_id:
            self._ad_hoc_session_id = None


class BulkSessions:
    def __init__(self, *, configuration, sessions, scan_session: Callable[[str], OrganizeSession]) -> None:
        self.configuration = configuration
        self.sessions = sessions
        self.scan_session = scan_session

    def create(self, origin_ids: list[str]) -> BulkSessionCreateResult:
        sessions: list[OrganizeSession] = []
        results: list[BulkSessionItem] = []
        seen: set[str] = set()
        for origin_id in origin_ids:
            if origin_id in seen:
                results.append(
                    BulkSessionItem(
                        origin_id=origin_id,
                        status=BulkSessionItemStatus.DUPLICATE,
                        message=f"Duplicate Origin in bulk request: {origin_id}",
                        code="origin.duplicate_request",
                        details={"origin_id": origin_id},
                    )
                )
                continue
            seen.add(origin_id)

            created_session_id: str | None = None
            try:
                origin = self.configuration.get_origin(origin_id)
                if origin.trigger == OriginTrigger.WATCH:
                    results.append(
                        BulkSessionItem(
                            origin_id=origin_id,
                            status=BulkSessionItemStatus.WATCH_ORIGIN,
                            message="Watched folders are automatic; use a manual Origin",
                            code="origin.watch_automatic",
                            details={"origin_id": origin_id, "origin_name": origin.name},
                        )
                    )
                    continue
                if not origin.enabled:
                    results.append(
                        BulkSessionItem(
                            origin_id=origin_id,
                            status=BulkSessionItemStatus.DISABLED,
                            message=f"Origin is disabled: {origin_id}",
                            code="origin.disabled",
                            details={"origin_id": origin_id, "origin_name": origin.name},
                        )
                    )
                    continue

                session = self.sessions.create_for_origin(origin)
                created_session_id = session.id
                scanned = self.scan_session(session.id)
                sessions.append(scanned)
                results.append(BulkSessionItem(origin_id=origin_id, status=BulkSessionItemStatus.CREATED, session_id=scanned.id))
            except OrganizeSessionConflict as exc:
                results.append(
                    BulkSessionItem(
                        origin_id=origin_id,
                        status=BulkSessionItemStatus.CONFLICT,
                        message=str(exc),
                        code=_error_code(exc),
                        details=_error_details(exc),
                    )
                )
            except ConfigurationError as exc:
                results.append(
                    BulkSessionItem(
                        origin_id=origin_id,
                        status=BulkSessionItemStatus.MISSING if _error_code(exc) == "origin.unknown" else BulkSessionItemStatus.INVALID,
                        message=str(exc),
                        code=_error_code(exc),
                        details=_error_details(exc),
                    )
                )
            except OmediaError as exc:
                if created_session_id:
                    self._cancel_created_session(created_session_id)
                results.append(
                    BulkSessionItem(
                        origin_id=origin_id,
                        status=BulkSessionItemStatus.INVALID,
                        message=str(exc),
                        code=_error_code(exc),
                        details=_error_details(exc),
                    )
                )
        return BulkSessionCreateResult(sessions=sessions, results=results)

    def _cancel_created_session(self, session_id: str) -> None:
        try:
            self.sessions.cancel(session_id)
        except OmediaError:
            return


def _session_id() -> str:
    return f"organize-session-{uuid4()}"


def _depot_for_ref(configuration, depot_ref: str) -> Depot:
    try:
        return configuration.get_depot(depot_ref)
    except ConfigurationError:
        for depot in configuration.list_depots():
            if depot.name.casefold() == depot_ref.strip().casefold():
                return depot
        raise ConfigurationError(f"No Depot configured for target: {depot_ref}")


def _error_code(exc: OmediaError) -> str | None:
    code = getattr(exc, "code", None)
    if hasattr(code, "value"):
        code = code.value
    return str(code) if code else None


def _error_details(exc: OmediaError) -> dict[str, object] | None:
    details = getattr(exc, "details", None)
    return dict(details) if details else None
