from __future__ import annotations

from pathlib import Path

from app.domain.activity import ActivityArea, ActivityStatus
from app.domain.media import MediaExtensionPolicy
from app.domain.origin import UNKNOWN_FOLDER_NAME, Origin
from app.domain.result import ResultStatus
from app.engines.activity.provenance import replacement_provenance
from app.infra.fs.move import move_with_replace
from app.infra.fs.result import StorageMoveStatus
from app.services.activity.recorder import ActivityRecorder
from app.services.watch.buffer import WatchDispatch


class WatchReturn:
    def __init__(
        self,
        *,
        activity: ActivityRecorder,
        extensions: MediaExtensionPolicy,
        origin: Origin,
        source_path: Path,
        dispatch: WatchDispatch | None = None,
        reason: str = "unmatched",
    ) -> None:
        self.activity = activity
        self.extensions = extensions
        self.origin = origin
        self.source_path = source_path
        self.destination_path = origin.path / UNKNOWN_FOLDER_NAME / source_path.name
        self.dispatch = dispatch
        self.reason = reason

    def move(self) -> ResultStatus:
        if not self.source_path.exists():
            self._record_missing()
            return ResultStatus.SKIPPED
        context = self._context()
        try:
            self.destination_path.parent.mkdir(parents=True, exist_ok=True)
            move_result = move_with_replace(
                self.source_path,
                self.destination_path,
                cleanup_root=self.origin.path,
                sidecar_extensions=self.extensions.sidecar,
            )
            context = {**context, **move_result.context()}
            if move_result.status == StorageMoveStatus.SUCCEEDED:
                self._record_success(context)
                return ResultStatus.SUCCEEDED
            status = ResultStatus.TIMEOUT if move_result.status == StorageMoveStatus.TIMEOUT else ResultStatus.FAILED
            self._record_move_failure(move_result, context)
            return status
        except Exception as exc:
            self._record_exception(exc, context)
            return ResultStatus.FAILED

    def _context(self) -> dict:
        return replacement_provenance(
            source_path=self.source_path,
            destination_path=self.destination_path,
            context={
                **watch_context(self.origin, self.source_path, self.destination_path, dispatch=self.dispatch),
                "unmatched": True,
                "rejected_source_package_reason": None if self.reason == "unmatched" else self.reason,
            },
        )

    def _record_missing(self) -> None:
        self.activity.record_return_item(
            area=ActivityArea.WATCH_ORGANIZE,
            status=ActivityStatus.SKIPPED,
            reason="source_missing",
            source_path=self.source_path,
            destination_path=self.destination_path,
            summary="Unmatched watch source no longer exists",
            origin=self.origin,
            context=watch_context(self.origin, self.source_path, self.destination_path, dispatch=self.dispatch),
        )

    def _record_success(self, context: dict) -> None:
        self.activity.record_return_item(
            area=ActivityArea.WATCH_ORGANIZE,
            status=ActivityStatus.SUCCEEDED,
            reason=self.reason,
            source_path=self.source_path,
            destination_path=self.destination_path,
            summary="Sent unmatched item to review" if self.reason == "unmatched" else "Sent rejected source package to review",
            origin=self.origin,
            context=context,
        )

    def _record_move_failure(self, move_result, context: dict) -> None:
        self.activity.record_return_item(
            area=ActivityArea.WATCH_ORGANIZE,
            status=ActivityStatus.FAILED,
            reason="timed_out" if move_result.status == StorageMoveStatus.TIMEOUT else move_result.error_type,
            source_path=self.source_path,
            destination_path=self.destination_path,
            summary=move_result.message,
            origin=self.origin,
            context={**context, "error_type": move_result.error_type},
        )

    def _record_exception(self, exc: Exception, context: dict) -> None:
        self.activity.record_return_item(
            area=ActivityArea.WATCH_ORGANIZE,
            status=ActivityStatus.FAILED,
            reason=type(exc).__name__,
            source_path=self.source_path,
            destination_path=self.destination_path,
            summary=str(exc),
            origin=self.origin,
            context={**context, "error_type": type(exc).__name__},
        )


def watch_context(
    origin: Origin,
    source_path: Path,
    destination_path: Path | None,
    *,
    dispatch: WatchDispatch | None = None,
) -> dict:
    context = {
        "origin_id": origin.id,
        "origin_name": origin.name,
        "origin_path": str(origin.path),
        "source_relative_path": relative_path_text(source_path, origin.path),
        "destination_relative_path": relative_path_text(destination_path, origin.path),
        "media_type": origin.media_type.value,
    }
    if dispatch is None:
        return context
    context.update(
        {
            "watch_event_path": str(dispatch.event_path),
            "watch_event_relative_path": relative_path_text(dispatch.event_path, origin.path),
            "watch_candidate_path": str(dispatch.candidate_path),
            "watch_candidate_relative_path": relative_path_text(dispatch.candidate_path, origin.path),
            "watch_dispatch_source": dispatch.source,
            "watch_event_type": dispatch.event_type,
            "watch_stability_snapshot_count": dispatch.stability_snapshot_count,
            "watch_stability_retry_count": dispatch.stability_retry_count,
            "trace_id": dispatch.trace_id,
            "watch_event_paths": [
                relative_path_text(path, origin.path) or path.name
                for path in dispatch.event_paths
            ],
        }
    )
    return context


def relative_path_text(path: Path | None, root: Path) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name
