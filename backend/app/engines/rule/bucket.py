from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Set as AbstractSet

from pypinyin import lazy_pinyin

from app.core.error import ConfigurationError
from app.engines.name.depot import safe_relative_fragment

RULE_BUCKET_VARIABLES = frozenset({"first_char", "decade"})
RULE_BUCKET_VARIABLE_PATTERN = re.compile(r"{([^{}]+)}")


def first_char_bucket(title: str) -> str:
    first = title.strip()[:1]
    if not first:
        return "0-9"
    if is_cjk(first):
        pinyin = lazy_pinyin(first)
        first = pinyin[0][:1] if pinyin else ""
    if first.isdigit():
        return "0-9"
    first = first.upper()
    return first if "A" <= first <= "Z" else "0-9"


def is_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def validate_rule_bucket(bucket: str, *, variables: AbstractSet[str] = RULE_BUCKET_VARIABLES) -> None:
    for variable in RULE_BUCKET_VARIABLE_PATTERN.findall(bucket or ""):
        if variable not in variables:
            raise ConfigurationError(f"Unsupported bucket variable: {variable}")
    safe_relative_fragment(bucket or "", allow_empty=True)


def render_rule_bucket(bucket: str, variables: Mapping[str, str] | Callable[[str], str]) -> str | None:
    try:
        rendered = RULE_BUCKET_VARIABLE_PATTERN.sub(lambda match: _bucket_variable_value(match.group(1), variables), bucket or "")
        if not rendered:
            return ""
        return safe_relative_fragment(rendered, allow_empty=True).as_posix()
    except (ConfigurationError, KeyError, ValueError):
        return None


def _bucket_variable_value(name: str, variables: Mapping[str, str] | Callable[[str], str]) -> str:
    if callable(variables):
        return variables(name)
    if name not in variables:
        raise KeyError(name)
    return variables[name]
