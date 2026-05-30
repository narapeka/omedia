from __future__ import annotations

from app.api.http.present.config import present_organize_policy
from app.api.http.schemas.config import Origin, OriginSummary


def present_origin(origin) -> Origin:
    return Origin(
        id=origin.id,
        name=origin.name,
        path=origin.path,
        media_type=origin.media_type,
        trigger=origin.trigger,
        enabled=origin.enabled,
        policy=present_organize_policy(origin.policy),
    )


def present_origin_summary(origin) -> OriginSummary:
    return OriginSummary(**present_origin(origin).model_dump())

