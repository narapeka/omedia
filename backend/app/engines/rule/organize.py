from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.error import ConfigurationError
from app.domain.rule import (
    OrganizeRule,
    RuleCondition,
    RuleOperator,
    RuleCategory,
    rule_condition_value_is_empty,
    rule_value_contains,
    rule_value_equals,
)
from app.engines.rule.bucket import first_char_bucket, render_rule_bucket, validate_rule_bucket

ORGANIZE_FIELD_OPERATORS = {
    "tmdb.genre_ids": {RuleOperator.CONTAINS, RuleOperator.IN},
    "tmdb.origin_country": {RuleOperator.CONTAINS, RuleOperator.IN},
    "tmdb.release_year": {RuleOperator.EQUALS, RuleOperator.IN_RANGE},
    "relative_path": {RuleOperator.CONTAINS, RuleOperator.MATCHES},
}
ORGANIZE_FIELDS = set(ORGANIZE_FIELD_OPERATORS)
ORGANIZE_OPERATORS = {operator for operators in ORGANIZE_FIELD_OPERATORS.values() for operator in operators}


@dataclass(frozen=True)
class OrganizeRuleContext:
    tmdb: dict[str, Any] = field(default_factory=dict)
    relative_path: Path | str = ""


@dataclass(frozen=True)
class OrganizeRuleResult:
    bucket: str
    matched_category: str | None = None
    warnings: list[str] = field(default_factory=list)


class OrganizeRuleEngine:
    def validate(self, rule: OrganizeRule) -> None:
        validate_organize_rule(rule)

    def match(self, rule: OrganizeRule | None, context: OrganizeRuleContext) -> OrganizeRuleResult:
        if rule is None:
            return OrganizeRuleResult(bucket="")
        validate_organize_rule(rule)
        for category in rule.categories:
            if not all(_condition_matches(condition, context) for condition in category.conditions):
                continue
            rendered = _try_render_bucket(category.bucket, context)
            if rendered is None:
                continue
            return OrganizeRuleResult(bucket=rendered, matched_category=category.name)
        fallback = _try_render_bucket(rule.fallback_bucket, context)
        return OrganizeRuleResult(bucket=fallback or "")


def validate_organize_rule(rule: OrganizeRule) -> None:
    for category in rule.categories:
        _validate_category(category)
        _validate_bucket(category.bucket)
        for condition in category.conditions:
            _validate_condition(condition)
    _validate_bucket(rule.fallback_bucket)


def _validate_category(category: RuleCategory) -> None:
    if not category.bucket.strip():
        raise ConfigurationError("OrganizeRule category bucket is required")
    if not category.conditions:
        raise ConfigurationError("OrganizeRule category conditions are required")


def _validate_condition(condition: RuleCondition) -> None:
    allowed_operators = ORGANIZE_FIELD_OPERATORS.get(condition.field)
    if allowed_operators is None:
        raise ConfigurationError(f"Unsupported OrganizeRule field: {condition.field}")
    if condition.op not in allowed_operators:
        raise ConfigurationError(f"Unsupported OrganizeRule operator for {condition.field}: {condition.op}")
    _validate_condition_value(condition)
    if condition.op == RuleOperator.MATCHES:
        re.compile(str(condition.value))
    if condition.op == RuleOperator.IN_RANGE:
        _range_bounds(condition.value)


def _validate_condition_value(condition: RuleCondition) -> None:
    if condition.op == RuleOperator.IN:
        values = condition.value if isinstance(condition.value, (list, tuple, set)) else [condition.value]
        if not values or any(rule_condition_value_is_empty(item) for item in values):
            raise ConfigurationError(f"OrganizeRule condition value is required for {condition.field}")
        return
    if rule_condition_value_is_empty(condition.value):
        raise ConfigurationError(f"OrganizeRule condition value is required for {condition.field}")


def _validate_bucket(bucket: str) -> None:
    validate_rule_bucket(bucket)


def _condition_matches(condition: RuleCondition, context: OrganizeRuleContext) -> bool:
    actual = _field_value(condition.field, context)
    expected = condition.value
    if condition.op == RuleOperator.CONTAINS:
        return rule_value_contains(actual, expected)
    if condition.op == RuleOperator.IN:
        return _in(actual, expected)
    if condition.op == RuleOperator.EQUALS:
        return rule_value_equals(actual, expected)
    if condition.op == RuleOperator.MATCHES:
        return re.search(str(expected), str(actual or ""), flags=re.IGNORECASE) is not None
    if condition.op == RuleOperator.IN_RANGE:
        return _in_range(actual, expected)
    return False


def _field_value(field: str, context: OrganizeRuleContext) -> Any:
    if field == "relative_path":
        return str(context.relative_path)
    if field == "tmdb.release_year":
        return _release_year(context.tmdb)
    key = field.removeprefix("tmdb.")
    return context.tmdb.get(key)


def _in(actual: Any, expected: Any) -> bool:
    expected_values = expected if isinstance(expected, (list, tuple, set)) else [expected]
    if isinstance(actual, (list, tuple, set)):
        return any(item in expected_values for item in actual)
    return actual in expected_values


def _in_range(actual: Any, expected: Any) -> bool:
    if actual is None:
        return False
    start, end = _range_bounds(expected)
    try:
        value = int(actual)
    except (TypeError, ValueError):
        return False
    return start <= value <= end


def _range_bounds(value: Any) -> tuple[int, int]:
    try:
        if isinstance(value, str):
            parts = re.split(r"\s*-\s*", value.strip(), maxsplit=1)
            if len(parts) != 2:
                raise ValueError
            left, right = parts
            return int(left), int(right)
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return int(value[0]), int(value[1])
    except (TypeError, ValueError):
        raise ConfigurationError(f"Invalid range value: {value}") from None
    raise ConfigurationError(f"Invalid range value: {value}")


def _try_render_bucket(bucket: str, context: OrganizeRuleContext) -> str | None:
    return render_rule_bucket(bucket, lambda name: _variable(name, context))


def _variable(name: str, context: OrganizeRuleContext) -> str:
    if name == "first_char":
        title = _title(context.tmdb)
        if not title:
            raise ValueError("missing title")
        return first_char_bucket(title)
    if name == "decade":
        year = _release_year(context.tmdb)
        if year is None:
            raise ValueError("missing release year")
        return str((int(year) // 10) * 10)
    raise ValueError(f"unsupported variable: {name}")


def _title(tmdb: dict[str, Any]) -> str | None:
    for key in ("title", "name", "original_title", "original_name"):
        value = tmdb.get(key)
        if value:
            return str(value)
    return None


def _release_year(tmdb: dict[str, Any]) -> int | None:
    for key in ("release_year", "year"):
        value = tmdb.get(key)
        if value:
            return int(value)
    for key in ("release_date", "first_air_date"):
        value = str(tmdb.get(key) or "")
        match = re.match(r"(\d{4})", value)
        if match:
            return int(match.group(1))
    return None
