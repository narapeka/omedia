from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.domain.depot import Depot, ResolveMode, TransferPolicy
from app.domain.media import MediaType
from app.domain.origin import OrganizePolicy, Origin, OriginTrigger
from app.domain.rule import OrganizeRule, RuleCategory, RuleCondition, RuleOperator, TransferRule
from app.domain.transfer import TransferTrigger
from app.domain.watch import WatchSettings


def provider_config_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "tmdb": dict(payload["tmdb"]),
        "llm": dict(payload["llm"]),
    }


def watch_settings_data(config: WatchSettings) -> dict[str, Any]:
    return {
        "id": config.id,
        "path": config.path,
        "enabled": config.enabled,
        "metadata": config.metadata,
    }


def watch_settings_from_data(payload: Mapping[str, Any]) -> WatchSettings:
    return WatchSettings(
        id=str(payload.get("id") or "main"),
        path=Path(payload["path"]),
        enabled=bool(payload.get("enabled", True)),
        metadata=dict(payload.get("metadata") or {}),
    )


def origin_data(origin: Origin) -> dict[str, Any]:
    return {
        "id": origin.id,
        "name": origin.name,
        "path": origin.path,
        "media_type": origin.media_type,
        "trigger": origin.trigger,
        "enabled": origin.enabled,
        "policy": {
            "target_depot_id": origin.policy.target_depot_id,
            "organize_rule_id": origin.policy.organize_rule_id,
        },
        "metadata": origin.metadata,
    }


def origin_from_data(payload: Mapping[str, Any]) -> Origin:
    policy = payload["policy"]
    return Origin(
        id=str(payload["id"]),
        name=str(payload["name"]).strip(),
        path=Path(payload["path"]),
        media_type=MediaType(payload["media_type"]),
        trigger=OriginTrigger(payload["trigger"]),
        enabled=bool(payload.get("enabled", True)),
        policy=OrganizePolicy(
            target_depot_id=str(policy["target_depot_id"]),
            organize_rule_id=policy.get("organize_rule_id"),
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


def depot_data(depot: Depot) -> dict[str, Any]:
    return {
        "id": depot.id,
        "name": depot.name,
        "path": depot.path,
        "media_type": depot.media_type,
        "enabled": depot.enabled,
        "resolve_mode": depot.resolve_mode,
        "policy": {
            "target_library_path": depot.policy.target_library_path,
            "trigger": depot.policy.trigger,
            "transfer_rule_id": depot.policy.transfer_rule_id,
            "schedule": depot.policy.schedule,
        },
        "metadata": depot.metadata,
    }


def depot_from_data(payload: Mapping[str, Any]) -> Depot:
    media_type = MediaType(payload["media_type"])
    policy = payload["policy"]
    return Depot(
        id=str(payload["id"]),
        name=str(payload["name"]).strip(),
        path=Path(payload["path"]),
        media_type=media_type,
        enabled=bool(payload.get("enabled", True)),
        resolve_mode=ResolveMode.FULL if media_type == MediaType.MOVIE else ResolveMode(payload.get("resolve_mode", "full")),
        policy=TransferPolicy(
            target_library_path=Path(policy["target_library_path"]),
            trigger=TransferTrigger(policy.get("trigger", "manual")),
            transfer_rule_id=policy.get("transfer_rule_id"),
            schedule=policy.get("schedule"),
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


def organize_rule_data(rule: OrganizeRule) -> dict[str, Any]:
    return rule_data(rule)


def transfer_rule_data(rule: TransferRule) -> dict[str, Any]:
    return rule_data(rule)


def rule_data(rule: OrganizeRule | TransferRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.name,
        "categories": [category_data(category) for category in rule.categories],
        "fallback_bucket": rule.fallback_bucket,
        "description": rule.description,
    }


def organize_rule_from_data(payload: Mapping[str, Any]) -> OrganizeRule:
    return OrganizeRule(
        id=str(payload["id"]),
        name=str(payload["name"]).strip(),
        categories=[category_from_data(category) for category in payload.get("categories", [])],
        fallback_bucket=str(payload.get("fallback_bucket") or ""),
        description=payload.get("description"),
    )


def transfer_rule_from_data(payload: Mapping[str, Any]) -> TransferRule:
    return TransferRule(
        id=str(payload["id"]),
        name=str(payload["name"]).strip(),
        categories=[category_from_data(category) for category in payload.get("categories", [])],
        fallback_bucket=str(payload.get("fallback_bucket") or ""),
        description=payload.get("description"),
    )


def category_data(category: RuleCategory) -> dict[str, Any]:
    return {
        "name": category.name,
        "bucket": category.bucket,
        "conditions": [
            {"field": condition.field, "op": condition.op, "value": condition.value}
            for condition in category.conditions
        ],
    }


def category_from_data(payload: Mapping[str, Any]) -> RuleCategory:
    return RuleCategory(
        name=str(payload["name"]),
        bucket=str(payload["bucket"]),
        conditions=[
            RuleCondition(field=str(item["field"]), op=RuleOperator(item["op"]), value=item.get("value"))
            for item in payload.get("conditions", [])
        ],
    )
