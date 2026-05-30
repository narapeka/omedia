from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import or_, select

from app.infra.db.models.activity import ActivityEventModel
from app.infra.db.models.base import format_dt
from app.domain.activity import ActivityAction, ActivityArea, ActivityEntityType, ActivityEvent, ActivityStatus

ATTENTION_REASONS = {
    "unmatched",
    "source_missing",
    "destination_exists",
    "resolve_disabled",
    "blocked",
    "timed_out",
    "depot_locked",
    "interrupted",
    "invalid_destination",
    "hard_timeout_stop",
}


class ActivityRecords:
    def save_activity_event(self, event: ActivityEvent) -> None:
        with self.session_scope() as session:
            session.merge(ActivityEventModel.from_domain(event))

    def get_activity_event(self, event_id: str) -> ActivityEvent | None:
        with self.session_factory() as session:
            model = session.get(ActivityEventModel, event_id)
            return model.to_domain() if model else None

    def list_activity_events(
        self,
        *,
        areas: Sequence[ActivityArea] | None = None,
        entity_type: ActivityEntityType | None = None,
        action: ActivityAction | None = None,
        status: ActivityStatus | None = None,
        reason: str | None = None,
        trace_id: str | None = None,
        origin_id: str | None = None,
        depot_id: str | None = None,
        library_path: str | None = None,
        media_type: str | None = None,
        tmdb_id: str | int | None = None,
        entity_source: str | None = None,
        entity_target: str | None = None,
        time_from: datetime | None = None,
        time_to: datetime | None = None,
        focus: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ActivityEvent]:
        stmt = select(ActivityEventModel)
        if areas:
            stmt = stmt.where(ActivityEventModel.area.in_([area.value for area in areas]))
        if entity_type:
            stmt = stmt.where(ActivityEventModel.entity_type == entity_type.value)
        if action:
            stmt = stmt.where(ActivityEventModel.action == action.value)
        if status:
            stmt = stmt.where(ActivityEventModel.status == status.value)
        if reason:
            stmt = stmt.where(ActivityEventModel.reason == reason)
        if trace_id:
            stmt = stmt.where(ActivityEventModel.trace_id == trace_id)
        if origin_id:
            stmt = stmt.where(ActivityEventModel.origin_id == origin_id)
        if depot_id:
            stmt = stmt.where(ActivityEventModel.depot_id == depot_id)
        if library_path:
            stmt = stmt.where(ActivityEventModel.library_path == library_path)
        if media_type:
            stmt = stmt.where(ActivityEventModel.media_type == media_type)
        if tmdb_id:
            stmt = stmt.where(ActivityEventModel.tmdb_id == str(tmdb_id))
        if entity_source:
            stmt = stmt.where(ActivityEventModel.entity_source == entity_source)
        if entity_target:
            stmt = stmt.where(ActivityEventModel.entity_target == entity_target)
        if time_from:
            stmt = stmt.where(ActivityEventModel.time >= format_dt(time_from))
        if time_to:
            stmt = stmt.where(ActivityEventModel.time <= format_dt(time_to))
        if focus == "attention":
            stmt = stmt.where(
                or_(
                    ActivityEventModel.status == ActivityStatus.FAILED.value,
                    ActivityEventModel.reason.in_(sorted(ATTENTION_REASONS)),
                )
            )
        elif focus == "failed":
            stmt = stmt.where(ActivityEventModel.status == ActivityStatus.FAILED.value)
        elif focus == "unmatched":
            stmt = stmt.where(ActivityEventModel.reason == "unmatched")
        stmt = stmt.order_by(ActivityEventModel.time.desc(), ActivityEventModel.id)
        if not (q and q.strip()):
            if offset:
                stmt = stmt.offset(offset)
            if limit:
                stmt = stmt.limit(limit)
        with self.session_factory() as session:
            events = [model.to_domain() for model in session.scalars(stmt).all()]

        if q and q.strip():
            needle = q.strip().casefold()
            events = [
                event for event in events
                if any(needle in value.casefold() for value in _event_search_values(event))
            ]
        start = offset or 0
        end = start + limit if limit else None
        return events[start:end]


def _event_search_values(event: ActivityEvent) -> list[str]:
    values = [
        event.entity_source or "",
        event.entity_target or "",
        event.summary or "",
        event.origin_name or "",
        str(event.origin_path) if event.origin_path else "",
        event.depot_name or "",
        str(event.depot_path) if event.depot_path else "",
        str(event.library_path) if event.library_path else "",
        event.rule_name or "",
        event.media_type or "",
        event.tmdb_id or "",
        event.reason or "",
    ]
    values.extend(_context_search_values(event.context or {}))
    return [value for value in values if value]


def _context_search_values(value: object, key: str | None = None) -> list[str]:
    if key and any(part in key.casefold() for part in ("job", "trace", "id")):
        return []
    if isinstance(value, dict):
        values: list[str] = []
        for child_key, child_value in value.items():
            values.extend(_context_search_values(child_value, str(child_key)))
        return values
    if isinstance(value, list):
        values: list[str] = []
        for item in value:
            values.extend(_context_search_values(item, key))
        return values
    if value is None:
        return []
    return [str(value)]
