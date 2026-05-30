from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

from app.domain.depot import Depot
from app.domain.media import MediaCandidate, MediaExtensionPolicy, MediaFile
from app.domain.organize import (
    OrganizeSessionState,
    SourceActionOperation,
    SourceActionStatus,
    source_file_id,
)
from app.domain.rule import OrganizeRule
from app.infra.fs.delete import StorageDeleteStatus, delete_verified_file, delete_verified_tree
from app.infra.fs.inspect import inspect_path
from app.infra.fs.rename import StorageRenameStatus, rename_verified_file, rename_verified_tree
from app.services.organize.candidate import (
    SourceCandidateKind,
    classify_source_file,
    file_state,
    find_media_candidate,
    find_source_file,
    require_active_candidate,
    source_candidate_kind,
    source_state,
    sum_optional,
)
from app.services.organize.plan import rebuild_source_candidate
from app.services.organize.review import ConflictReviews
from app.services.organize.session import (
    DeleteMetadata,
    OrganizeSession,
    OrganizeSessionError,
    SourceCandidateStatus,
    SourceFileState,
    SourceFileStatus,
    require_state,
)


def source_candidate_detail(task: OrganizeSession, source_candidate_id: str):
    candidate = find_media_candidate(task, source_candidate_id)
    detail = inspect_path(candidate.candidate_path, protected_root=task.path)
    state = source_state(task, source_candidate_id)
    if not detail.exists:
        state.status = SourceCandidateStatus.UNAVAILABLE
    elif detail.blocked_reason:
        state.status = SourceCandidateStatus.BLOCKED
        state.blocked_reason = detail.blocked_reason
    return detail


def source_file_detail(
    task: OrganizeSession,
    source_candidate_id: str,
    file_id: str,
    *,
    extensions: MediaExtensionPolicy,
) -> dict[str, object]:
    candidate, file = find_source_file(task, source_candidate_id, file_id)
    detail = inspect_path(file.path, protected_root=task.path)
    state = file_state(task, source_candidate_id, file)
    if not detail.exists:
        state.status = SourceFileStatus.MISSING
    elif detail.blocked_reason:
        state.status = SourceFileStatus.BLOCKED
        state.blocked_reason = detail.blocked_reason
    return {
        "path": file.path,
        "exists": detail.exists,
        "file_type": detail.file_type,
        "size_bytes": detail.size_bytes,
        "created_time": detail.created_time,
        "modified_time": detail.modified_time,
        "classification": classify_source_file(file, state, extensions),
        "source_candidate_id": candidate.id,
        "source_candidate_display_name": candidate.display_name,
        "source_candidate_kind": source_candidate_kind(candidate),
        "source_candidate_status": source_state(task, candidate.id).status,
        "source_candidate_path": candidate.candidate_path,
        "source_root": candidate.source_root,
        "file_count": len(candidate.files),
        "total_size": sum_optional(file.size_bytes for file in candidate.files),
        "source_file_id": file_id,
        "relative_path": file.relative_path,
        "blocked_reason": detail.blocked_reason,
    }


class SourceEdit:
    def __init__(
        self,
        task: OrganizeSession,
        source_candidate_id: str,
        *,
        extensions: MediaExtensionPolicy | None = None,
        organize_rule: OrganizeRule | None = None,
        tv_episode_planner=None,
        target_depot: Depot | None = None,
    ) -> None:
        self.task = task
        self.source_candidate_id = source_candidate_id
        self.extensions = extensions
        self.organize_rule = organize_rule
        self.tv_episode_planner = tv_episode_planner
        self.target_depot = target_depot

    def rename_file(self, file_id: str, new_name: str) -> OrganizeSession:
        self._require_editable()
        ConflictReviews(self.task, target_depot=self.target_depot).require_file_operation_allowed(self.source_candidate_id, file_id)
        candidate = self._active_candidate()
        _candidate, file = find_source_file(self.task, self.source_candidate_id, file_id)
        state = file_state(self.task, self.source_candidate_id, file)
        self._require_active_file(state, file_id)

        result = rename_verified_file(file.path, new_name, protected_root=self.task.path)
        if result.status != StorageRenameStatus.SUCCEEDED:
            self._mark_rename_file_failure(state, result)
            raise _source_action_error(result, operation="rename")

        old_file_id = file_id
        new_file = _renamed_media_file(candidate, file, result.new_path, extensions=self._extensions())
        _replace_candidate_file(candidate, file, new_file)
        if candidate.candidate_path == result.old_path:
            candidate.candidate_path = result.new_path
            candidate.display_name = result.new_path.stem

        new_file_id = source_file_id(candidate.id, new_file.relative_path)
        _remap_file_state(self.task, old_file_id, new_file_id, state)
        _update_plan_items_for_renamed_file(self.task, old_file_id, new_file_id, new_file)
        self._record_rename(result, old_file_id=old_file_id, new_file_id=new_file_id)
        self._rebuild_if_identified()
        return self.task

    def rename_candidate(self, new_name: str) -> OrganizeSession:
        self._require_editable()
        ConflictReviews(self.task, target_depot=self.target_depot).require_file_operation_allowed(self.source_candidate_id, None)
        candidate = self._active_candidate()

        if source_candidate_kind(candidate) == SourceCandidateKind.MOVIE_FILE:
            if not candidate.files:
                raise OrganizeSessionError(f"Source candidate has no files: {self.source_candidate_id}")
            file_id = source_file_id(candidate.id, candidate.files[0].relative_path)
            return self.rename_file(file_id, new_name)

        result = rename_verified_tree(candidate.candidate_path, new_name, protected_root=self.task.path)
        if result.status != StorageRenameStatus.SUCCEEDED:
            self._mark_rename_candidate_failure(result)
            raise _source_action_error(result, operation="rename")

        old_path = result.old_path
        candidate.candidate_path = result.new_path
        candidate.display_name = result.new_path.name
        candidate.files = [
            _refreshed_media_file(replace(file, path=result.new_path / file.relative_path), extensions=self._extensions())
            for file in candidate.files
        ]
        _update_plan_items_for_renamed_candidate(self.task, candidate, old_path)
        self._record_rename(result, old_file_id=None, new_file_id=None)
        self._rebuild_if_identified()
        return self.task

    def delete_file(self, file_id: str) -> OrganizeSession:
        self._require_editable()
        ConflictReviews(self.task, target_depot=self.target_depot).require_file_operation_allowed(self.source_candidate_id, file_id)
        self._active_candidate()
        _candidate, file = find_source_file(self.task, self.source_candidate_id, file_id)
        state = file_state(self.task, self.source_candidate_id, file)
        self._require_active_file(state, file_id)
        result = delete_verified_file(file.path, protected_root=self.task.path)
        if result.status == StorageDeleteStatus.SUCCEEDED:
            state.status = SourceFileStatus.DELETED
            state.delete_metadata = DeleteMetadata(
                scope=result.scope,
                file_count=result.file_count,
                total_size=result.total_size,
            )
            self._record_delete(result, file_id=file_id)
            self._rebuild()
            return self.task
        if result.status == StorageDeleteStatus.MISSING:
            state.status = SourceFileStatus.MISSING
        elif result.status == StorageDeleteStatus.BLOCKED:
            state.status = SourceFileStatus.BLOCKED
            state.blocked_reason = result.blocked_reason
        raise _source_action_error(result, operation="delete")

    def delete_candidate(self) -> OrganizeSession:
        self._require_editable()
        candidate = self._active_candidate()
        state = source_state(self.task, self.source_candidate_id)
        result = delete_verified_tree(candidate.candidate_path, protected_root=self.task.path)
        if result.status == StorageDeleteStatus.SUCCEEDED:
            state.status = SourceCandidateStatus.DELETED
            state.delete_metadata = DeleteMetadata(
                scope=result.scope,
                file_count=result.file_count,
                total_size=result.total_size,
            )
            for file in candidate.files:
                state_for_file = file_state(self.task, self.source_candidate_id, file)
                state_for_file.status = SourceFileStatus.DELETED
                state_for_file.delete_metadata = state.delete_metadata
            self.task.plan_items = [item for item in self.task.plan_items if item.source_candidate_id != self.source_candidate_id]
            reviews = ConflictReviews(self.task)
            reviews.drop_source(self.source_candidate_id)
            reviews.drop_stale()
            self._record_delete(result, file_id=None)
            return self.task
        if result.status == StorageDeleteStatus.MISSING:
            state.status = SourceCandidateStatus.UNAVAILABLE
        elif result.status == StorageDeleteStatus.BLOCKED:
            state.status = SourceCandidateStatus.BLOCKED
            state.blocked_reason = result.blocked_reason
        raise _source_action_error(result, operation="delete")

    def _active_candidate(self) -> MediaCandidate:
        return require_active_candidate(self.task, self.source_candidate_id)

    def _extensions(self) -> MediaExtensionPolicy:
        if self.extensions is None:
            raise OrganizeSessionError("Source file edit requires media extension policy")
        return self.extensions

    def _require_editable(self) -> None:
        require_state(self.task, {OrganizeSessionState.SCANNED, OrganizeSessionState.IDENTIFIED})

    def _require_active_file(self, state: SourceFileState, file_id: str) -> None:
        if state.status != SourceFileStatus.ACTIVE:
            raise OrganizeSessionError(
                f"Source file is {state.status.value}: {file_id}",
                code="source_file.not_editable",
                details={
                    "source_file_id": file_id,
                    "status": state.status.value,
                    "blocked_reason": state.blocked_reason,
                },
            )

    def _mark_rename_file_failure(self, state: SourceFileState, result) -> None:
        if result.status == StorageRenameStatus.MISSING:
            state.status = SourceFileStatus.MISSING
        elif result.status == StorageRenameStatus.BLOCKED:
            state.status = SourceFileStatus.BLOCKED
            state.blocked_reason = result.blocked_reason

    def _mark_rename_candidate_failure(self, result) -> None:
        state = source_state(self.task, self.source_candidate_id)
        if result.status == StorageRenameStatus.MISSING:
            state.status = SourceCandidateStatus.UNAVAILABLE
        elif result.status == StorageRenameStatus.BLOCKED:
            state.status = SourceCandidateStatus.BLOCKED
            state.blocked_reason = result.blocked_reason

    def _record_rename(self, result, *, old_file_id: str | None, new_file_id: str | None) -> None:
        outcome = rename_outcome(
            result,
            source_candidate_id=self.source_candidate_id,
            old_file_id=old_file_id,
            new_file_id=new_file_id,
        )
        self.task.last_source_action_outcome = outcome

    def _record_delete(self, result, *, file_id: str | None) -> None:
        outcome = delete_outcome(result, source_candidate_id=self.source_candidate_id, file_id=file_id)
        self.task.last_source_action_outcome = outcome

    def _rebuild_if_identified(self) -> None:
        if self.task.state == OrganizeSessionState.IDENTIFIED:
            self._rebuild()

    def _rebuild(self) -> None:
        rebuild_source_candidate(
            self.task,
            self.source_candidate_id,
            extensions=self._extensions(),
            organize_rule=self.organize_rule,
            tv_episode_planner=self.tv_episode_planner,
            target_depot=self.target_depot,
        )

def _source_action_error(result, *, operation: str) -> OrganizeSessionError:
    scope = "source_file" if result.scope == "file" else "source_candidate"
    if result.status.value == "missing":
        code = f"{scope}.missing"
    elif operation == "rename":
        code = f"{scope}.rename_blocked"
    else:
        code = f"{scope}.delete_blocked"
    message = f"{result.message}: {result.blocked_reason}" if result.blocked_reason else result.message
    return OrganizeSessionError(
        message,
        code=code,
        details={
            "scope": result.scope,
            "status": result.status.value,
            "path": str(result.old_path),
            "target_path": str(getattr(result, "new_path", "") or ""),
            "blocked_reason": result.blocked_reason,
            "error_type": getattr(result, "error_type", None),
        },
    )

def _renamed_media_file(
    candidate: MediaCandidate,
    file: MediaFile,
    new_path: Path,
    *,
    extensions: MediaExtensionPolicy,
) -> MediaFile:
    relative_root = candidate.source_root if candidate.candidate_path == file.path else candidate.candidate_path
    try:
        relative_path = new_path.relative_to(relative_root)
    except ValueError:
        relative_path = Path(new_path.name)
    return _refreshed_media_file(replace(file, path=new_path, relative_path=relative_path), extensions=extensions)

def _refreshed_media_file(file: MediaFile, *, extensions: MediaExtensionPolicy) -> MediaFile:
    extension = file.path.suffix.lower()
    try:
        stat = file.path.stat()
        size_bytes = stat.st_size
        modified_time = stat.st_mtime
    except OSError:
        size_bytes = file.size_bytes
        modified_time = file.modified_time
    return replace(
        file,
        extension=extension,
        size_bytes=size_bytes,
        modified_time=modified_time,
        is_sidecar=extension in extensions.sidecar_like,
    )

def _replace_candidate_file(candidate: MediaCandidate, old_file: MediaFile, new_file: MediaFile) -> None:
    for index, candidate_file in enumerate(candidate.files):
        if candidate_file.path == old_file.path and candidate_file.relative_path == old_file.relative_path:
            candidate.files[index] = new_file
            return
    raise OrganizeSessionError(f"Source file is no longer attached to candidate: {old_file.path}")

def _remap_file_state(task: OrganizeSession, old_file_id: str, new_file_id: str, state: SourceFileState) -> None:
    if old_file_id == new_file_id:
        task.file_states.setdefault(new_file_id, state)
        return
    current = task.file_states.pop(old_file_id, state)
    task.file_states[new_file_id] = current

def _update_plan_items_for_renamed_file(
    task: OrganizeSession,
    old_file_id: str,
    new_file_id: str,
    file: MediaFile,
) -> None:
    for item in task.plan_items:
        if item.source_file_id != old_file_id:
            continue
        item.source_file_id = new_file_id
        item.source_path = file.path
        item.source_size = file.size_bytes
        item.source_mtime = file.modified_time

def _update_plan_items_for_renamed_candidate(task: OrganizeSession, candidate: MediaCandidate, old_path: Path) -> None:
    files_by_id = {source_file_id(candidate.id, file.relative_path): file for file in candidate.files}
    for item in task.plan_items:
        if item.source_candidate_id != candidate.id:
            continue
        file = files_by_id.get(item.source_file_id)
        if file is not None:
            item.source_path = file.path
            item.source_size = file.size_bytes
            item.source_mtime = file.modified_time
            continue
        try:
            relative = item.source_path.relative_to(old_path)
        except ValueError:
            continue
        item.source_path = candidate.candidate_path / relative


@dataclass(frozen=True)
class SourceActionOutcome:
    operation: SourceActionOperation
    status: SourceActionStatus
    scope: str
    source_candidate_id: str
    source_file_id: str | None
    old_source_file_id: str | None
    new_source_file_id: str | None
    message: str
    file_count: int
    total_size: int
    old_path: Path
    new_path: Path | None
    exists_after: bool | None = None
    exists_after_old: bool | None = None
    exists_after_new: bool | None = None
    blocked_reason: str | None = None


@dataclass(frozen=True)
class SourceActionActivity:
    operation: SourceActionOperation
    status: SourceActionStatus
    blocked_reason: str | None
    message: str | None
    source_path: Path
    destination_path: Path | None
    context: dict[str, object]


def delete_outcome(result, *, source_candidate_id: str, file_id: str | None) -> SourceActionOutcome:
    return SourceActionOutcome(
        operation=SourceActionOperation.DELETE,
        status=SourceActionStatus(result.status.value),
        scope=result.scope,
        source_candidate_id=source_candidate_id,
        source_file_id=file_id,
        old_source_file_id=file_id,
        new_source_file_id=None,
        message=result.message,
        file_count=result.file_count,
        total_size=result.total_size,
        old_path=result.source_path,
        new_path=None,
        exists_after=result.exists_after,
        exists_after_old=result.exists_after,
        exists_after_new=None,
        blocked_reason=result.blocked_reason,
    )


def rename_outcome(result, *, source_candidate_id: str, old_file_id: str | None, new_file_id: str | None) -> SourceActionOutcome:
    return SourceActionOutcome(
        operation=SourceActionOperation.RENAME,
        status=SourceActionStatus(result.status.value),
        scope=result.scope,
        source_candidate_id=source_candidate_id,
        source_file_id=new_file_id or old_file_id,
        old_source_file_id=old_file_id,
        new_source_file_id=new_file_id,
        message=result.message,
        file_count=result.file_count,
        total_size=result.total_size,
        old_path=result.old_path,
        new_path=result.new_path,
        exists_after=None,
        exists_after_old=result.exists_after_old,
        exists_after_new=result.exists_after_new,
        blocked_reason=result.blocked_reason,
    )


def source_action_activity(session: OrganizeSession, outcome: SourceActionOutcome | Mapping[str, object]) -> SourceActionActivity | None:
    operation = _source_action_operation(_payload_get(outcome, "operation"))
    if operation is None:
        return None
    source_path = _payload_get(outcome, "old_path")
    if not isinstance(source_path, Path):
        return None
    destination_path = _payload_get(outcome, "new_path")
    return SourceActionActivity(
        operation=operation,
        status=_source_action_status(_payload_get(outcome, "status")) or SourceActionStatus.FAILED,
        blocked_reason=_optional_text(_payload_get(outcome, "blocked_reason")),
        message=_optional_text(_payload_get(outcome, "message")),
        source_path=source_path,
        destination_path=destination_path if isinstance(destination_path, Path) else None,
        context={
            "trace_id": session.id,
            "origin_id": session.origin_id,
            "origin_path": str(session.path) if session.origin_id else None,
            "source_candidate_id": _payload_get(outcome, "source_candidate_id"),
            "source_file_id": _payload_get(outcome, "source_file_id"),
            "old_source_file_id": _payload_get(outcome, "old_source_file_id"),
            "new_source_file_id": _payload_get(outcome, "new_source_file_id"),
            "scope": _payload_get(outcome, "scope"),
            "affected_file_count": _payload_get(outcome, "file_count"),
            "total_size_bytes": _payload_get(outcome, "total_size"),
            "blocked_reason": _payload_get(outcome, "blocked_reason"),
            "media_type": session.media_type.value,
        },
    )


def _payload_get(payload: SourceActionOutcome | Mapping[str, object], key: str) -> object:
    if isinstance(payload, Mapping):
        return payload.get(key)
    return getattr(payload, key)


def _optional_text(value: object) -> str | None:
    value = _payload_value(value)
    return str(value) if value is not None and str(value) else None


def _source_action_operation(value: object) -> SourceActionOperation | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        return SourceActionOperation(text)
    except ValueError:
        return None


def _source_action_status(value: object) -> SourceActionStatus | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        return SourceActionStatus(text)
    except ValueError:
        return None


def _payload_value(value: object) -> object:
    return value.value if isinstance(value, Enum) else value
