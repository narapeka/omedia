from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from uuid import uuid4

from app.domain.activity import ActivityEvent, ActivityStatus
from app.domain.depot import (
    Depot,
    DepotCandidate,
    DepotCandidateAction,
    DepotCandidateActionOutcome,
    DepotCandidateActionScope,
    DepotCandidateActionStatus,
    DepotCandidateFile,
    DepotCandidateKind,
    depot_candidate_file_id,
    depot_candidate_id,
)
from app.domain.media import MediaExtensionPolicy
from app.domain.transfer import TransferErrorCode
from app.engines.scan.depot import scan_depot_detail_tree
from app.engines.scan.types import DepotDetailScan
from app.infra.fs.delete import delete_verified_file, delete_verified_tree
from app.infra.fs.delete import DeleteResult
from app.infra.fs.inspect import FileDetail, inspect_path
from app.infra.fs.rename import rename_verified_file, rename_verified_tree
from app.infra.fs.rename import RenameResult
from app.services.activity.recorder import ActivityRecorder
from app.services.depot.candidate import CandidateBook, sort_depot_candidates_for_read
from app.services.depot.lock import DepotLockRegistry
from app.services.depot.returns import DepotReturn
from app.services.transfer.worker import TransferRejected


@dataclass(frozen=True)
class DepotCandidateDetailResult:
    candidate: DepotCandidate
    detail: FileDetail


@dataclass(frozen=True)
class DepotCandidateFileDetailResult:
    candidate: DepotCandidate
    file: DepotCandidateFile
    detail: FileDetail


@dataclass(frozen=True)
class DepotCandidateMutation:
    outcome: DepotCandidateActionOutcome


class DepotService:
    """Owns Depot file management and return actions."""

    def __init__(
        self,
        *,
        locks: DepotLockRegistry,
        activity: ActivityRecorder,
        store=None,
        extensions: MediaExtensionPolicy | None = None,
        sidecar_extensions=frozenset(),
    ):
        self.locks = locks
        self.activity = activity
        self.store = store
        self.extensions = extensions
        self.sidecar_extensions = frozenset(sidecar_extensions)

    def candidate_detail(self, depot: Depot, candidate_id: str) -> DepotCandidateDetailResult:
        candidate = self._candidates(depot).require(candidate_id)
        detail = inspect_path(candidate.path, protected_root=depot.path)
        return DepotCandidateDetailResult(candidate=candidate, detail=detail)

    def depot_detail(self, depot: Depot) -> DepotDetailScan:
        return self._depot_detail(depot)

    def transfer_history(self, depot: Depot, *, limit: int = 20):
        if self.store is None:
            return []
        return self.store.list_transfer_jobs(depot_id=depot.id, limit=limit)

    def candidate_rename(self, depot: Depot, candidate_id: str, new_name: str) -> DepotCandidateMutation:
        self._reject_if_transfer_busy(depot)
        with self.locks.acquire(depot):
            self._reject_if_transfer_busy(depot)
            candidate = self._candidates(depot).require(candidate_id)
            result = (
                rename_verified_file(candidate.path, new_name, protected_root=depot.path)
                if candidate.kind == DepotCandidateKind.FILE
                else rename_verified_tree(candidate.path, new_name, protected_root=depot.path)
            )
            outcome = _rename_outcome(depot, candidate, result)
            self._write_candidate_activity(depot, outcome, result.old_path, result.new_path, trace_id=_action_trace_id())
            return DepotCandidateMutation(outcome=outcome)

    def candidate_delete(self, depot: Depot, candidate_id: str) -> DepotCandidateMutation:
        self._reject_if_transfer_busy(depot)
        with self.locks.acquire(depot):
            self._reject_if_transfer_busy(depot)
            candidate = self._candidates(depot).require(candidate_id)
            result = (
                delete_verified_file(candidate.path, protected_root=depot.path)
                if candidate.kind == DepotCandidateKind.FILE
                else delete_verified_tree(candidate.path, protected_root=depot.path)
            )
            outcome = _delete_outcome(depot, candidate, result)
            self._write_candidate_activity(depot, outcome, candidate.path, None, trace_id=_action_trace_id())
            return DepotCandidateMutation(outcome=outcome)

    def candidate_file_detail(self, depot: Depot, candidate_id: str, file_id: str) -> DepotCandidateFileDetailResult:
        candidate, file = self._candidates(depot).file(candidate_id, file_id)
        detail = inspect_path(file.path, protected_root=depot.path)
        return DepotCandidateFileDetailResult(candidate=candidate, file=file, detail=detail)

    def candidate_file_rename(self, depot: Depot, candidate_id: str, file_id: str, new_name: str) -> DepotCandidateMutation:
        self._reject_if_transfer_busy(depot)
        with self.locks.acquire(depot):
            self._reject_if_transfer_busy(depot)
            candidate, file = self._candidates(depot).file(candidate_id, file_id)
            result = rename_verified_file(file.path, new_name, protected_root=depot.path)
            outcome = _file_rename_outcome(depot, candidate, file_id, result)
            self._write_candidate_activity(depot, outcome, result.old_path, result.new_path, trace_id=_action_trace_id())
            return DepotCandidateMutation(outcome=outcome)

    def candidate_file_delete(self, depot: Depot, candidate_id: str, file_id: str) -> DepotCandidateMutation:
        self._reject_if_transfer_busy(depot)
        with self.locks.acquire(depot):
            self._reject_if_transfer_busy(depot)
            candidate, file = self._candidates(depot).file(candidate_id, file_id)
            result = delete_verified_file(file.path, protected_root=depot.path)
            outcome = _file_delete_outcome(depot, candidate, file_id, file.path, result)
            self._write_candidate_activity(depot, outcome, file.path, None, trace_id=_action_trace_id())
            return DepotCandidateMutation(outcome=outcome)

    def return_items(
        self,
        depot: Depot,
        relative_paths: list[Path],
        destination_root: Path,
        *,
        candidate_ids: list[str] | None = None,
    ) -> list[ActivityEvent]:
        self._reject_if_transfer_busy(depot)
        entries: list[ActivityEvent] = []
        trace_id = _action_trace_id()
        depot_return = DepotReturn(activity=self.activity)
        with self.locks.acquire(depot):
            self._reject_if_transfer_busy(depot)
            if candidate_ids:
                for candidate in self._candidates(depot).many(candidate_ids):
                    if candidate.blocked_reason:
                        entries.append(depot_return.blocked_candidate(depot, candidate, destination_root, trace_id=trace_id))
                        continue
                    entries.append(depot_return.path(depot, candidate.relative_path, destination_root, source_path=candidate.path, trace_id=trace_id))
            else:
                for relative_path in relative_paths:
                    entries.append(depot_return.path(depot, relative_path, destination_root, trace_id=trace_id))
        return entries

    def _write_candidate_activity(
        self,
        depot: Depot,
        outcome: DepotCandidateActionOutcome,
        source_path: Path | None,
        destination_path: Path | None,
        *,
        trace_id: str,
    ) -> ActivityEvent:
        status, reason = _activity_status_reason(outcome)
        context = {
            "depot_id": depot.id,
            "depot_name": depot.name,
            "depot_path": str(depot.path),
            "depot_candidate_id": outcome.candidate_id,
            "old_depot_candidate_id": outcome.old_candidate_id,
            "new_depot_candidate_id": outcome.new_candidate_id,
            "depot_candidate_file_id": outcome.file_id,
            "old_depot_candidate_file_id": outcome.old_file_id,
            "new_depot_candidate_file_id": outcome.new_file_id,
            "depot_scope": outcome.scope.value,
            "depot_action_status": outcome.status.value,
            "depot_relative_path": _relative_path_text(source_path, depot.path) if source_path else None,
            "destination_relative_path": _relative_path_text(destination_path, depot.path) if destination_path else None,
            "affected_file_count": outcome.affected_file_count,
            "total_size_bytes": outcome.total_size_bytes,
            "blocked_reason": outcome.blocked_reason,
            "media_type": depot.media_type.value,
        }
        if outcome.action == DepotCandidateAction.RENAME:
            return self.activity.record_rename(
                source_path=source_path,
                destination_path=destination_path,
                status=status,
                reason=reason,
                summary=outcome.message,
                trace_id=trace_id,
                depot=depot,
                context=context,
            )
        return self.activity.record_delete(
            source_path=source_path,
            status=status,
            reason=reason,
            summary=outcome.message,
            trace_id=trace_id,
            depot=depot,
            context=context,
        )

    def _reject_if_transfer_busy(self, depot: Depot) -> None:
        if self.store is not None and self.store.active_transfer_job_for_depot(depot.id):
            raise TransferRejected(
                TransferErrorCode.DEPOT_TRANSFER_BUSY,
                "Depot already has pending or running transfer",
                details={"depot_id": depot.id, "depot_name": depot.name},
            )

    def _depot_detail(self, depot: Depot) -> DepotDetailScan:
        detail = scan_depot_detail_tree(depot, self._extensions())
        return replace(detail, candidates=sort_depot_candidates_for_read(detail.candidates))

    def _candidates(self, depot: Depot) -> CandidateBook:
        return CandidateBook(depot, self._extensions())

    def _extensions(self) -> MediaExtensionPolicy:
        if self.extensions is None:
            raise RuntimeError("Depot candidate operations require media extension settings")
        return self.extensions


def _rename_outcome(depot: Depot, candidate: DepotCandidate, result: RenameResult) -> DepotCandidateActionOutcome:
    new_candidate_id = None
    if result.succeeded:
        new_candidate_id = depot_candidate_id(depot.id, candidate.kind, result.new_path.relative_to(depot.path))
    return DepotCandidateActionOutcome(
        action=DepotCandidateAction.RENAME,
        scope=DepotCandidateActionScope.CANDIDATE,
        status=DepotCandidateActionStatus(result.status.value),
        depot_id=depot.id,
        candidate_id=candidate.id,
        old_candidate_id=candidate.id,
        new_candidate_id=new_candidate_id,
        old_path=result.old_path,
        new_path=result.new_path,
        affected_file_count=result.file_count,
        total_size_bytes=result.total_size,
        message=result.message,
        blocked_reason=result.blocked_reason or result.error_type,
    )


def _delete_outcome(depot: Depot, candidate: DepotCandidate, result: DeleteResult) -> DepotCandidateActionOutcome:
    return DepotCandidateActionOutcome(
        action=DepotCandidateAction.DELETE,
        scope=DepotCandidateActionScope.CANDIDATE,
        status=DepotCandidateActionStatus(result.status.value),
        depot_id=depot.id,
        candidate_id=candidate.id,
        old_candidate_id=candidate.id,
        old_path=result.source_path,
        affected_file_count=result.file_count,
        total_size_bytes=result.total_size,
        message=result.message,
        blocked_reason=result.blocked_reason or result.error_type,
    )


def _file_rename_outcome(depot: Depot, candidate: DepotCandidate, file_id: str, result: RenameResult) -> DepotCandidateActionOutcome:
    new_file_id = depot_candidate_file_id(depot.id, result.new_path.relative_to(depot.path)) if result.succeeded else None
    return DepotCandidateActionOutcome(
        action=DepotCandidateAction.RENAME,
        scope=DepotCandidateActionScope.FILE,
        status=DepotCandidateActionStatus(result.status.value),
        depot_id=depot.id,
        candidate_id=candidate.id,
        file_id=file_id,
        old_file_id=file_id,
        new_file_id=new_file_id,
        old_path=result.old_path,
        new_path=result.new_path,
        affected_file_count=result.file_count,
        total_size_bytes=result.total_size,
        message=result.message,
        blocked_reason=result.blocked_reason or result.error_type,
    )


def _file_delete_outcome(
    depot: Depot,
    candidate: DepotCandidate,
    file_id: str,
    file_path: Path,
    result: DeleteResult,
) -> DepotCandidateActionOutcome:
    return DepotCandidateActionOutcome(
        action=DepotCandidateAction.DELETE,
        scope=DepotCandidateActionScope.FILE,
        status=DepotCandidateActionStatus(result.status.value),
        depot_id=depot.id,
        candidate_id=candidate.id,
        file_id=file_id,
        old_file_id=file_id,
        old_path=file_path,
        affected_file_count=result.file_count,
        total_size_bytes=result.total_size,
        message=result.message,
        blocked_reason=result.blocked_reason or result.error_type,
    )


def _activity_status_reason(outcome: DepotCandidateActionOutcome) -> tuple[ActivityStatus, str | None]:
    if outcome.status == DepotCandidateActionStatus.SUCCEEDED:
        return ActivityStatus.SUCCEEDED, None
    if outcome.status == DepotCandidateActionStatus.MISSING:
        return ActivityStatus.SKIPPED, "source_missing"
    if outcome.status == DepotCandidateActionStatus.BLOCKED:
        return ActivityStatus.SKIPPED, "blocked"
    if outcome.status == DepotCandidateActionStatus.CONFLICT:
        return ActivityStatus.SKIPPED, "destination_exists"
    return ActivityStatus.FAILED, outcome.blocked_reason


def _relative_path_text(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _action_trace_id() -> str:
    return f"file-action-{uuid4()}"
