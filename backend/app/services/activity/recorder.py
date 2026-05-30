from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.activity import ActivityAction, ActivityArea, ActivityEntityType, ActivityEvent, ActivityStatus
from app.services.activity import context as activity_context

class ActivityRecorder:
    def __init__(
        self,
        store,
        *,
        id_factory: Callable[[], str] | None = None,
        now: Callable[[], datetime] | None = None,
    ):
        self.store = store
        self.id_factory = id_factory or (lambda: f"activity-{uuid4()}")
        self.now = now or (lambda: datetime.now(timezone.utc))

    def record_event(
        self,
        *,
        area: ActivityArea | str,
        entity_type: ActivityEntityType | str,
        action: ActivityAction | str,
        status: ActivityStatus | str,
        reason: str | None = None,
        summary: str | None = None,
        trace_id: str | None = None,
        entity_source: str | Path | None = None,
        entity_target: str | Path | None = None,
        origin: "Origin | None" = None,
        depot: "Depot | None" = None,
        library_path: Path | None = None,
        rule: "OrganizeRule | TransferRule | None" = None,
        media_type: str | None = None,
        tmdb_id: str | int | None = None,
        context: dict[str, Any] | None = None,
    ) -> ActivityEvent:
        curated_context = activity_context.curated(context or {})
        context_tmdb_id = activity_context.tmdb_id(curated_context)
        event = ActivityEvent(
            id=self.id_factory(),
            time=self.now(),
            area=ActivityArea(area),
            entity_type=ActivityEntityType(entity_type),
            action=ActivityAction(action),
            status=ActivityStatus(status),
            reason=reason or activity_context.reason(curated_context),
            summary=summary,
            trace_id=trace_id or activity_context.text(curated_context.get("trace_id")),
            entity_source=activity_context.entity_text(entity_source),
            entity_target=activity_context.entity_text(entity_target),
            origin_id=activity_context.origin_id(origin, curated_context),
            origin_name=activity_context.origin_name(origin, curated_context),
            origin_path=activity_context.origin_path(origin, curated_context),
            depot_id=activity_context.depot_id(depot, curated_context),
            depot_name=activity_context.depot_name(depot, curated_context),
            depot_path=activity_context.depot_path(depot, curated_context),
            library_path=library_path or activity_context.library_path(depot, curated_context),
            rule_id=activity_context.rule_id(rule, curated_context),
            rule_name=activity_context.rule_name(rule, curated_context),
            media_type=media_type or activity_context.media_type(origin, depot, curated_context),
            tmdb_id=str(tmdb_id or context_tmdb_id) if (tmdb_id or context_tmdb_id) else None,
            context=curated_context,
        )
        self.store.save_activity_event(event)
        return event

    def record_depot_item(
        self,
        *,
        area: ActivityArea,
        status: ActivityStatus,
        source_path: Path,
        destination_path: Path | None,
        depot: "Depot | None" = None,
        origin: "Origin | None" = None,
        reason: str | None = None,
        summary: str | None = None,
        trace_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ActivityEvent:
        return self.record_event(
            area=area,
            entity_type=activity_context.entity_type(source_path, destination_path, context),
            action=ActivityAction.MOVE_TO_DEPOT,
            status=status,
            reason=reason,
            summary=summary,
            trace_id=trace_id,
            entity_source=source_path,
            entity_target=destination_path,
            origin=origin,
            depot=depot,
            context=context,
        )

    def record_return_item(
        self,
        *,
        area: ActivityArea,
        status: ActivityStatus,
        source_path: Path,
        destination_path: Path | None,
        depot: "Depot | None" = None,
        origin: "Origin | None" = None,
        reason: str | None = None,
        summary: str | None = None,
        trace_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ActivityEvent:
        return self.record_event(
            area=area,
            entity_type=activity_context.entity_type(source_path, destination_path, context),
            action=ActivityAction.RETURN,
            status=status,
            reason=reason,
            summary=summary,
            trace_id=trace_id,
            entity_source=source_path,
            entity_target=destination_path,
            origin=origin,
            depot=depot,
            context=context,
        )

    def record_transfer_item(
        self,
        *,
        area: ActivityArea,
        status: ActivityStatus,
        source_path: Path,
        destination_path: Path | None,
        depot: "Depot | None",
        reason: str | None = None,
        summary: str | None = None,
        trace_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ActivityEvent:
        return self.record_event(
            area=area,
            entity_type=ActivityEntityType.FILE,
            action=ActivityAction.TRANSFER,
            status=status,
            reason=reason,
            summary=summary,
            trace_id=trace_id,
            entity_source=source_path,
            entity_target=destination_path,
            depot=depot,
            context=context,
        )

    def record_transfer_job_event(
        self,
        *,
        job: "TransferJob",
        depot: "Depot | None" = None,
        status: ActivityStatus,
        reason: str | None = None,
        summary: str | None = None,
        action: ActivityAction = ActivityAction.TRANSFER,
        context: dict[str, Any] | None = None,
    ) -> ActivityEvent:
        area = activity_context.transfer_area(job.requested_by)
        return self.record_event(
            area=area,
            entity_type=ActivityEntityType.TRANSFER_JOB,
            action=action,
            status=status,
            reason=reason,
            summary=summary,
            trace_id=job.id,
            entity_source=depot.path if depot else job.depot_id,
            entity_target=depot.policy.target_library_path if depot else None,
            depot=depot,
            context={"transfer_job_status": job.status.value, **(context or {})},
        )

    def record_session_event(
        self,
        *,
        area: ActivityArea,
        entity_type: ActivityEntityType,
        action: ActivityAction,
        status: ActivityStatus,
        trace_id: str,
        summary: str | None = None,
        entity_source: str | Path | None = None,
        entity_target: str | Path | None = None,
        origin: "Origin | None" = None,
        depot: "Depot | None" = None,
        context: dict[str, Any] | None = None,
    ) -> ActivityEvent:
        return self.record_event(
            area=area,
            entity_type=entity_type,
            action=action,
            status=status,
            summary=summary,
            trace_id=trace_id,
            entity_source=entity_source or activity_context.session_source(origin, depot, context),
            entity_target=entity_target or activity_context.session_target(depot, context),
            origin=origin,
            depot=depot,
            context=context,
        )

    def record_rename(
        self,
        *,
        source_path: Path,
        destination_path: Path | None,
        status: ActivityStatus,
        reason: str | None = None,
        summary: str | None = None,
        trace_id: str | None = None,
        origin: "Origin | None" = None,
        depot: "Depot | None" = None,
        context: dict[str, Any] | None = None,
    ) -> ActivityEvent:
        return self.record_event(
            area=ActivityArea.FILE_MANAGEMENT,
            entity_type=activity_context.entity_type(source_path, destination_path, context),
            action=ActivityAction.RENAME,
            status=status,
            reason=reason,
            summary=summary,
            trace_id=trace_id,
            entity_source=source_path,
            entity_target=destination_path,
            origin=origin,
            depot=depot,
            context=context,
        )

    def record_delete(
        self,
        *,
        source_path: Path,
        status: ActivityStatus,
        reason: str | None = None,
        summary: str | None = None,
        trace_id: str | None = None,
        origin: "Origin | None" = None,
        depot: "Depot | None" = None,
        context: dict[str, Any] | None = None,
    ) -> ActivityEvent:
        return self.record_event(
            area=ActivityArea.FILE_MANAGEMENT,
            entity_type=activity_context.entity_type(source_path, None, context),
            action=ActivityAction.DELETE,
            status=status,
            reason=reason,
            summary=summary,
            trace_id=trace_id,
            entity_source=source_path,
            origin=origin,
            depot=depot,
            context=context,
        )

    def record_cancel(
        self,
        *,
        area: ActivityArea,
        entity_type: ActivityEntityType,
        status: ActivityStatus,
        reason: str = "user_cancelled",
        summary: str | None = None,
        trace_id: str | None = None,
        depot: "Depot | None" = None,
        context: dict[str, Any] | None = None,
    ) -> ActivityEvent:
        return self.record_event(
            area=area,
            entity_type=entity_type,
            action=ActivityAction.CANCEL,
            status=status,
            reason=reason,
            summary=summary,
            trace_id=trace_id,
            entity_source=depot.path if depot else None,
            entity_target=depot.policy.target_library_path if depot else None,
            depot=depot,
            context=context,
        )
