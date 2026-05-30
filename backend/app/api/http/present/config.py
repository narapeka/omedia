from __future__ import annotations

from app.api.http.schemas.config import (
    SettingsHealth,
    OrganizePolicy,
    OrganizeRule,
    RuleCondition,
    RulePreview,
    RuleCategory,
    TransferRule,
)


def present_settings_health(health) -> SettingsHealth:
    return SettingsHealth(
        ok=health.ok,
        database=health.database,
        config_loaded=health.config_loaded,
        origins=health.origins,
        depots=health.depots,
        organize_rules=health.organize_rules,
        transfer_rules=health.transfer_rules,
        watched_folders=health.watched_folders,
        scheduled_transfers=health.scheduled_transfers,
    )


def present_organize_rule(rule) -> OrganizeRule:
    return OrganizeRule(
        id=rule.id,
        name=rule.name,
        categories=[present_rule_category(category) for category in rule.categories],
        fallback_bucket=rule.fallback_bucket,
        description=rule.description,
    )


def present_transfer_rule(rule) -> TransferRule:
    return TransferRule(
        id=rule.id,
        name=rule.name,
        categories=[present_rule_category(category) for category in rule.categories],
        fallback_bucket=rule.fallback_bucket,
        description=rule.description,
    )


def present_rule_category(category) -> RuleCategory:
    return RuleCategory(
        name=category.name,
        bucket=category.bucket,
        conditions=[
            RuleCondition(field=condition.field, op=condition.op, value=condition.value)
            for condition in category.conditions
        ],
    )


def present_rule_preview(result) -> RulePreview:
    return RulePreview(
        bucket=result.bucket,
        matched_category=result.matched_category,
        warnings=getattr(result, "warnings", []),
        variables=getattr(result, "variables", {}),
    )


def present_organize_policy(policy) -> OrganizePolicy:
    return OrganizePolicy(
        target_depot_id=policy.target_depot_id,
        organize_rule_id=policy.organize_rule_id,
    )

