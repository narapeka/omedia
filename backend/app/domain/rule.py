from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuleOperator(str, Enum):
    CONTAINS = "contains"
    IN = "in"
    EQUALS = "equals"
    MATCHES = "matches"
    IN_RANGE = "in_range"


@dataclass(frozen=True)
class RuleCondition:
    field: str
    op: RuleOperator
    value: Any


@dataclass(frozen=True)
class RuleCategory:
    name: str
    bucket: str
    conditions: list[RuleCondition] = field(default_factory=list)


@dataclass(frozen=True)
class OrganizeRule:
    id: str
    name: str
    categories: list[RuleCategory] = field(default_factory=list)
    fallback_bucket: str = ""
    description: str | None = None


@dataclass(frozen=True)
class TransferRule:
    id: str
    name: str
    categories: list[RuleCategory] = field(default_factory=list)
    fallback_bucket: str = ""
    description: str | None = None


def rule_condition_value_is_empty(value: Any) -> bool:
    if isinstance(value, (list, tuple, set)):
        return not value or any(rule_condition_value_is_empty(item) for item in value)
    return value is None or (isinstance(value, str) and not value.strip())


def rule_value_equals(actual: Any, expected: Any) -> bool:
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.casefold() == expected.casefold()
    return actual == expected


def rule_value_contains(actual: Any, expected: Any) -> bool:
    if actual is None:
        return False
    if isinstance(actual, (list, tuple, set)):
        return any(rule_value_equals(item, expected) for item in actual)
    return str(expected).casefold() in str(actual).casefold()
