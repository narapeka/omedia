from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.http.deps import Config
from app.api.http.present.origin import present_origin, present_origin_summary
from app.api.http.schemas.common import DEFAULT_API_RESPONSES
from app.api.http.schemas.config import Origin as OriginModel, OriginDraft, OriginSummary
from app.domain.ids import new_object_id
from app.domain.media import MediaType
from app.domain.origin import OrganizePolicy as DomainOrganizePolicy, Origin as DomainOrigin, OriginTrigger

router = APIRouter(prefix="/origins", tags=["origins"], responses=DEFAULT_API_RESPONSES)


@router.get("", response_model=list[OriginSummary])
def list_origins(config: Config) -> list[OriginSummary]:
    return [present_origin_summary(origin) for origin in config.list_origins()]


@router.get("/{origin_id}", response_model=OriginSummary)
def origin_detail(origin_id: str, config: Config) -> OriginSummary:
    return present_origin_summary(config.get_origin(origin_id))


@router.post("", response_model=OriginModel)
def create_origin(payload: OriginDraft, config: Config) -> OriginModel:
    origin = _origin_from_schema(payload, origin_id=new_object_id("origin"))
    saved = config.save_origin(origin)
    return present_origin(saved)


@router.put("/{origin_id}", response_model=OriginModel)
def save_origin(origin_id: str, payload: OriginDraft, config: Config) -> OriginModel:
    origin = _origin_from_schema(payload, origin_id=origin_id)
    saved = config.save_origin(origin)
    return present_origin(saved)


@router.delete("/{origin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_origin(origin_id: str, config: Config) -> Response:
    config.delete_origin(origin_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _origin_from_schema(payload: OriginDraft, *, origin_id: str) -> DomainOrigin:
    return DomainOrigin(
        id=origin_id,
        name=payload.name.strip(),
        path=payload.path,
        media_type=MediaType(payload.media_type),
        trigger=OriginTrigger(payload.trigger),
        enabled=payload.enabled,
        policy=DomainOrganizePolicy(
            target_depot_id=payload.policy.target_depot_id,
            organize_rule_id=payload.policy.organize_rule_id,
        ),
    )
