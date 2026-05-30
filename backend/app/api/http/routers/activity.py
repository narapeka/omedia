from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Query

from app.api.http.deps import Activity
from app.api.http.present.activity import present_activity_event
from app.api.http.schemas.activity import ActivityEventList, ActivityEvent
from app.api.http.schemas.common import DEFAULT_API_RESPONSES
from app.domain.activity import ActivityAction, ActivityArea, ActivityEntityType, ActivityFocus, ActivityGroup, ActivityStatus

router = APIRouter(prefix="/activity", tags=["activity"], responses=DEFAULT_API_RESPONSES)


@router.get("/events", response_model=ActivityEventList)
def list_activity_event_history(
    activity: Activity,
    q: str | None = Query(default=None, min_length=1),
    area: list[ActivityArea] | None = Query(default=None),
    group: ActivityGroup | None = None,
    entity_type: ActivityEntityType | None = None,
    action: ActivityAction | None = None,
    status: ActivityStatus | None = None,
    reason: str | None = None,
    origin_id: str | None = None,
    depot_id: str | None = None,
    library_path: Path | None = Query(default=None),
    media_type: Literal["movie", "tv"] | None = None,
    tmdb_id: str | None = None,
    focus: ActivityFocus | None = None,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    path: Path | None = Query(default=None),
) -> ActivityEventList:
    if path:
        events = activity.provenance_for_path(path)
        window = events[offset:offset + limit + 1]
    else:
        window = activity.list_activity(
            areas=area,
            group=group,
            entity_type=entity_type,
            action=action,
            status=status,
            reason=reason,
            origin_id=origin_id,
            depot_id=depot_id,
            library_path=library_path,
            media_type=media_type,
            tmdb_id=tmdb_id,
            focus=focus,
            q=q,
            time_from=from_at,
            time_to=to_at,
            limit=limit + 1,
            offset=offset,
        )
    return ActivityEventList(
        items=[present_activity_event(event) for event in window[:limit]],
        limit=limit,
        offset=offset,
        has_more=len(window) > limit,
    )


@router.get("/events/{event_id}", response_model=ActivityEvent)
def activity_event_detail(event_id: str, activity: Activity) -> ActivityEvent:
    return present_activity_event(activity.get_activity_event(event_id))
