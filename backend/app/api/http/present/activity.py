from __future__ import annotations

from app.api.http.schemas.activity import ActivityEvent


def present_activity_event(event) -> ActivityEvent:
    return ActivityEvent(
        id=event.id,
        time=event.time,
        area=event.area,
        entity_type=event.entity_type,
        action=event.action,
        status=event.status,
        reason=event.reason,
        summary=event.summary,
        entity_source=event.entity_source,
        entity_target=event.entity_target,
        origin_id=event.origin_id,
        origin_name=event.origin_name,
        origin_path=event.origin_path,
        depot_id=event.depot_id,
        depot_name=event.depot_name,
        depot_path=event.depot_path,
        rule_id=event.rule_id,
        rule_name=event.rule_name,
        library_path=event.library_path,
        media_type=event.media_type,
        tmdb_id=event.tmdb_id,
        trace_id=event.trace_id,
        context=dict(event.context or {}),
    )
