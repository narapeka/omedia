from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.core.error import ConfigurationError
from app.domain.rule import (
    RuleCondition,
    RuleOperator,
    RuleCategory,
    TransferRule,
    rule_condition_value_is_empty,
    rule_value_contains,
)
from app.engines.name.depot import split_depot_relative_path
from app.engines.rule.bucket import first_char_bucket, render_rule_bucket, validate_rule_bucket

TRANSFER_FIELD_OPERATORS = {
    "relative_path": {
        RuleOperator.CONTAINS,
        RuleOperator.MATCHES,
    },
}
TRANSFER_FIELDS = set(TRANSFER_FIELD_OPERATORS)
TRANSFER_OPERATORS = {operator for operators in TRANSFER_FIELD_OPERATORS.values() for operator in operators}
SYSTEM_FOLDER_PATTERN = re.compile(r"^(?P<title>.+?)(?: \((?P<year>\d{4})\))?(?: \{tmdb-\d+\})?$")


@dataclass(frozen=True)
class TransferRuleContext:
    relative_path: Path | str
    media_relative_path: Path | str | None = None
    organize_prefix: Path | str | None = None


@dataclass(frozen=True)
class TransferRuleResult:
    bucket: str
    matched_category: str | None = None
    variables: dict[str, str] = field(default_factory=dict)


class TransferRuleEngine:
    def validate(self, rule: TransferRule) -> None:
        validate_transfer_rule(rule)

    def match(self, rule: TransferRule | None, context: TransferRuleContext) -> TransferRuleResult:
        variables = _parse_variables(context)
        if rule is None:
            return TransferRuleResult(bucket="", variables=variables)
        validate_transfer_rule(rule)
        for category in rule.categories:
            if not all(_condition_matches(condition, context) for condition in category.conditions):
                continue
            rendered = _try_render_bucket(category.bucket, variables)
            if rendered is None:
                continue
            return TransferRuleResult(bucket=rendered, matched_category=category.name, variables=variables)
        fallback = _try_render_bucket(rule.fallback_bucket, variables)
        return TransferRuleResult(bucket=fallback or "", variables=variables)


def validate_transfer_rule(rule: TransferRule) -> None:
    for category in rule.categories:
        _validate_category(category)
        _validate_bucket(category.bucket)
        for condition in category.conditions:
            _validate_condition(condition)
    _validate_bucket(rule.fallback_bucket)


def _validate_category(category: RuleCategory) -> None:
    if not category.bucket.strip():
        raise ConfigurationError("TransferRule category bucket is required")
    if not category.conditions:
        raise ConfigurationError("TransferRule category conditions are required")


def _validate_condition(condition: RuleCondition) -> None:
    allowed_operators = TRANSFER_FIELD_OPERATORS.get(condition.field)
    if allowed_operators is None:
        raise ConfigurationError(f"Unsupported TransferRule field: {condition.field}")
    if condition.op not in allowed_operators:
        raise ConfigurationError(f"Unsupported TransferRule operator for {condition.field}: {condition.op}")
    if rule_condition_value_is_empty(condition.value):
        raise ConfigurationError(f"TransferRule condition value is required for {condition.field}")
    if condition.op == RuleOperator.MATCHES:
        re.compile(str(condition.value))


def _validate_bucket(bucket: str) -> None:
    validate_rule_bucket(bucket)


def _condition_matches(condition: RuleCondition, context: TransferRuleContext) -> bool:
    actual = _condition_relative_path(context)
    expected = condition.value
    if condition.op == RuleOperator.CONTAINS:
        return rule_value_contains(actual, expected)
    if condition.op == RuleOperator.MATCHES:
        return re.search(str(expected), actual, flags=re.IGNORECASE) is not None
    return False


def _condition_relative_path(context: TransferRuleContext) -> str:
    split = split_depot_relative_path(context.relative_path)
    if split.media_root_name:
        if split.organize_prefix.parts:
            return (split.organize_prefix / split.media_root_name).as_posix()
        return split.media_root_name
    if split.media_root_relative_path is not None:
        return split.media_root_relative_path.as_posix()
    return split.depot_relative_path.as_posix()


def _try_render_bucket(bucket: str, variables: dict[str, str]) -> str | None:
    return render_rule_bucket(bucket, variables)


def _parse_variables(context: TransferRuleContext | Path | str) -> dict[str, str]:
    if isinstance(context, TransferRuleContext):
        media_relative_path = context.media_relative_path or split_depot_relative_path(context.relative_path).media_relative_path
    else:
        media_relative_path = split_depot_relative_path(context).media_relative_path
    parts = Path(media_relative_path).parts
    if not parts:
        return {}
    media_root_name = Path(parts[0]).stem if len(parts) == 1 and Path(parts[0]).suffix else parts[0]
    match = SYSTEM_FOLDER_PATTERN.match(media_root_name)
    if not match:
        return {}
    variables: dict[str, str] = {}
    title = match.group("title")
    year = match.group("year")
    if title:
        variables["first_char"] = first_char_bucket(title)
    if year:
        variables["decade"] = str((int(year) // 10) * 10)
    return variables


