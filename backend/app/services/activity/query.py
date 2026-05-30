from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.domain.activity import (
    ActivityAction,
    ActivityArea,
    ActivityEntityType,
    ActivityEvent,
    ActivityFocus,
    ActivityGroup,
    ActivityStatus,
)
from app.domain.depot import Depot

GROUP_AREAS: dict[str, tuple[ActivityArea, ...]] = {
    "organize": (ActivityArea.MANUAL_ORGANIZE, ActivityArea.WATCH_ORGANIZE),
    "transfer": (ActivityArea.MANUAL_TRANSFER, ActivityArea.SCHEDULED_TRANSFER),
    "file_operations": (ActivityArea.FILE_MANAGEMENT,),
    "automation": (ActivityArea.WATCH_ORGANIZE, ActivityArea.SCHEDULED_TRANSFER),
}


class ActivityQueryService:
    def __init__(self, store):
        self.store = store

    def list_activity(
        self,
        *,
        areas: list[ActivityArea] | None = None,
        group: ActivityGroup | None = None,
        entity_type: ActivityEntityType | None = None,
        action: ActivityAction | None = None,
        status: ActivityStatus | None = None,
        reason: str | None = None,
        origin_id: str | None = None,
        depot_id: str | None = None,
        library_path: Path | None = None,
        media_type: str | None = None,
        tmdb_id: int | str | None = None,
        focus: ActivityFocus | None = None,
        q: str | None = None,
        time_from: datetime | None = None,
        time_to: datetime | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ActivityEvent]:
        selected_areas = tuple(areas or ())
        if group:
            group_areas = GROUP_AREAS[group]
            if selected_areas:
                selected_areas = tuple(area for area in selected_areas if area in group_areas)
                if not selected_areas:
                    return []
            else:
                selected_areas = group_areas
        return self.store.list_activity_events(
            areas=selected_areas,
            entity_type=entity_type,
            action=action,
            status=status,
            reason=reason,
            origin_id=origin_id,
            depot_id=depot_id,
            library_path=str(library_path) if library_path else None,
            media_type=media_type,
            tmdb_id=tmdb_id,
            focus=focus,
            q=q,
            time_from=time_from,
            time_to=time_to,
            limit=limit,
            offset=offset,
        )

    def provenance_for_path(self, path: Path) -> list[ActivityEvent]:
        text = str(path)
        by_source = self.store.list_activity_events(entity_source=text)
        by_target = self.store.list_activity_events(entity_target=text)
        seen: set[str] = set()
        events: list[ActivityEvent] = []
        for event in [*by_source, *by_target]:
            if event.id in seen:
                continue
            seen.add(event.id)
            events.append(event)
        return sorted(events, key=lambda event: event.time, reverse=True)

    def get_activity_event(self, event_id: str) -> ActivityEvent:
        event = self.store.get_activity_event(event_id)
        if event is not None:
            return event
        raise ValueError(f"Unknown ActivityEvent: {event_id}")

    def depot_file_provenance(self, Depot: Depot, relative_path: Path | str) -> list[ActivityEvent]:
        return self.provenance_for_path(Depot.path / Path(relative_path))
