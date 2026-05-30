from __future__ import annotations

from pathlib import Path

from app.domain.activity import ActivityArea, ActivityEvent, ActivityStatus
from app.domain.depot import Depot, DepotCandidate
from app.engines.activity.provenance import replacement_provenance
from app.infra.fs.move import move_with_replace
from app.infra.fs.result import StorageMoveStatus
from app.services.activity.recorder import ActivityRecorder


class DepotReturn:
    def __init__(
        self,
        *,
        activity: ActivityRecorder,
        sidecar_extensions=frozenset(),
    ) -> None:
        self.activity = activity
        self.sidecar_extensions = frozenset(sidecar_extensions)

    def blocked_candidate(
        self,
        depot: Depot,
        candidate: DepotCandidate,
        destination_root: Path,
        *,
        trace_id: str,
    ) -> ActivityEvent:
        destination = destination_root / candidate.relative_path
        return self.activity.record_return_item(
            area=ActivityArea.FILE_MANAGEMENT,
            status=ActivityStatus.SKIPPED,
            reason="blocked",
            source_path=candidate.path,
            destination_path=destination,
            summary="Depot candidate is blocked",
            trace_id=trace_id,
            depot=depot,
            context={
                **return_context(depot, candidate.relative_path, destination, destination_root),
                "depot_candidate_id": candidate.id,
                "depot_candidate_kind": candidate.kind.value,
                "blocked_reason": candidate.blocked_reason,
            },
        )

    def path(
        self,
        depot: Depot,
        relative_path: Path,
        destination_root: Path,
        *,
        source_path: Path | None = None,
        trace_id: str,
    ) -> ActivityEvent:
        source = source_path or depot.path / relative_path
        destination = destination_root / relative_path
        if not source.exists():
            return self.activity.record_return_item(
                area=ActivityArea.FILE_MANAGEMENT,
                status=ActivityStatus.SKIPPED,
                reason="source_missing",
                source_path=source,
                destination_path=destination,
                summary="Depot candidate no longer exists",
                trace_id=trace_id,
                depot=depot,
                context=return_context(depot, relative_path, destination, destination_root),
            )
        overwritten = destination.exists()
        context = replacement_provenance(
            source_path=source,
            destination_path=destination,
            context=return_context(depot, relative_path, destination, destination_root),
        )
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            move_result = move_with_replace(
                source,
                destination,
                cleanup_root=depot.path,
                sidecar_extensions=self.sidecar_extensions,
            )
            context = {**context, **move_result.context()}
            if move_result.status == StorageMoveStatus.SUCCEEDED:
                return self.activity.record_return_item(
                    area=ActivityArea.FILE_MANAGEMENT,
                    status=ActivityStatus.SUCCEEDED,
                    source_path=source,
                    destination_path=destination,
                    summary="Returned with replacement" if overwritten else "Returned",
                    trace_id=trace_id,
                    depot=depot,
                    context=context,
                )
            return self.activity.record_return_item(
                area=ActivityArea.FILE_MANAGEMENT,
                status=ActivityStatus.FAILED,
                reason="timed_out" if move_result.status == StorageMoveStatus.TIMEOUT else move_result.error_type,
                source_path=source,
                destination_path=destination,
                summary=move_result.message,
                trace_id=trace_id,
                depot=depot,
                context={**context, "error_type": move_result.error_type},
            )
        except Exception as exc:
            return self.activity.record_return_item(
                area=ActivityArea.FILE_MANAGEMENT,
                status=ActivityStatus.FAILED,
                reason=type(exc).__name__,
                source_path=source,
                destination_path=destination,
                summary=str(exc),
                trace_id=trace_id,
                depot=depot,
                context={**context, "error_type": type(exc).__name__},
            )


def return_context(depot: Depot, relative_path: Path, destination: Path, destination_root: Path) -> dict:
    return {
        "depot_id": depot.id,
        "depot_path": str(depot.path),
        "target_library_path": str(depot.policy.target_library_path),
        "depot_relative_path": relative_path.as_posix(),
        "destination_relative_path": _relative_path_text(destination, destination_root),
        "media_type": depot.media_type.value,
    }


def _relative_path_text(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name
