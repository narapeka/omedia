from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.http.deps import Config
from app.api.http.present.config import present_organize_rule, present_rule_preview, present_transfer_rule
from app.api.http.schemas.common import DEFAULT_API_RESPONSES
from app.api.http.schemas.config import (
    OrganizeRule as OrganizeRuleModel,
    OrganizeRuleDraft,
    OrganizeRulePreviewRequest,
    RulePreview,
    RuleReferences,
    TransferRule as TransferRuleModel,
    TransferRuleDraft,
    TransferRulePreviewRequest,
)
from app.domain.ids import new_object_id
from app.domain.rule import (
    OrganizeRule as DomainOrganizeRule,
    RuleCategory as DomainRuleCategory,
    RuleCondition as DomainRuleCondition,
    RuleOperator,
    TransferRule as DomainTransferRule,
)

router = APIRouter(prefix="/rules", tags=["rules"], responses=DEFAULT_API_RESPONSES)


@router.get("/references", response_model=RuleReferences)
def rule_references(config: Config) -> RuleReferences:
    return RuleReferences(**config.rule_references())


@router.get("/organize", response_model=list[OrganizeRuleModel])
def list_organize_rules(config: Config) -> list[OrganizeRuleModel]:
    return [present_organize_rule(rule) for rule in config.list_organize_rules()]


@router.post("/organize", response_model=OrganizeRuleModel)
def create_organize_rule(payload: OrganizeRuleDraft, config: Config) -> OrganizeRuleModel:
    rule = _organize_rule_from_schema(payload, rule_id=new_object_id("organize_rule"))
    return present_organize_rule(config.save_organize_rule(rule))


@router.post("/organize/preview", response_model=RulePreview)
def preview_organize_rule(payload: OrganizeRulePreviewRequest, config: Config) -> RulePreview:
    rule = _organize_rule_from_schema(payload.rule)
    result = config.preview_organize_rule(rule, tmdb=payload.tmdb, relative_path=payload.relative_path)
    return present_rule_preview(result)


@router.put("/organize/{rule_id}", response_model=OrganizeRuleModel)
def save_organize_rule(rule_id: str, payload: OrganizeRuleDraft, config: Config) -> OrganizeRuleModel:
    rule = _organize_rule_from_schema(payload, rule_id=rule_id)
    return present_organize_rule(config.save_organize_rule(rule))


@router.delete("/organize/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organize_rule(rule_id: str, config: Config) -> Response:
    config.delete_organize_rule(rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/transfer", response_model=list[TransferRuleModel])
def list_transfer_rules(config: Config) -> list[TransferRuleModel]:
    return [present_transfer_rule(rule) for rule in config.list_transfer_rules()]


@router.post("/transfer", response_model=TransferRuleModel)
def create_transfer_rule(payload: TransferRuleDraft, config: Config) -> TransferRuleModel:
    rule = _transfer_rule_from_schema(payload, rule_id=new_object_id("transfer_rule"))
    return present_transfer_rule(config.save_transfer_rule(rule))


@router.post("/transfer/preview", response_model=RulePreview)
def preview_transfer_rule(payload: TransferRulePreviewRequest, config: Config) -> RulePreview:
    rule = _transfer_rule_from_schema(payload.rule)
    result, path = config.preview_transfer_rule_path(rule, relative_path=payload.relative_path)
    response = present_rule_preview(result)
    response.transfer_bucket = path.transfer_bucket
    response.organize_prefix = path.organize_prefix
    response.media_relative_path = path.media_relative_path
    response.destination_relative_path = path.destination_relative_path
    response.path_split_confidence = path.path_split_confidence
    return response


@router.put("/transfer/{rule_id}", response_model=TransferRuleModel)
def save_transfer_rule(rule_id: str, payload: TransferRuleDraft, config: Config) -> TransferRuleModel:
    rule = _transfer_rule_from_schema(payload, rule_id=rule_id)
    return present_transfer_rule(config.save_transfer_rule(rule))


@router.delete("/transfer/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transfer_rule(rule_id: str, config: Config) -> Response:
    config.delete_transfer_rule(rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _organize_rule_from_schema(payload: OrganizeRuleDraft | OrganizeRuleModel, *, rule_id: str | None = None) -> DomainOrganizeRule:
    resolved_id = rule_id or getattr(payload, "id", None) or new_object_id("organize_rule")
    return DomainOrganizeRule(
        id=resolved_id,
        name=payload.name.strip(),
        categories=[_category_from_schema(category) for category in payload.categories],
        fallback_bucket=payload.fallback_bucket,
        description=payload.description,
    )


def _transfer_rule_from_schema(payload: TransferRuleDraft | TransferRuleModel, *, rule_id: str | None = None) -> DomainTransferRule:
    resolved_id = rule_id or getattr(payload, "id", None) or new_object_id("transfer_rule")
    return DomainTransferRule(
        id=resolved_id,
        name=payload.name.strip(),
        categories=[_category_from_schema(category) for category in payload.categories],
        fallback_bucket=payload.fallback_bucket,
        description=payload.description,
    )


def _category_from_schema(payload) -> DomainRuleCategory:
    return DomainRuleCategory(
        name=payload.name,
        bucket=payload.bucket,
        conditions=[DomainRuleCondition(field=item.field, op=RuleOperator(item.op), value=item.value) for item in payload.conditions],
    )
