from __future__ import annotations

import re
from typing import Sequence

try:
    from opencc import OpenCC
except ImportError:  # pragma: no cover - optional dependency
    OpenCC = None

CHINESE_CHARACTER_PATTERN = re.compile(r"[\u4e00-\u9fff]")
CHINESE_ORIGINAL_LANGUAGES = frozenset({"zh", "cn", "yue"})
PREFERRED_CHINESE_REGIONS = ("CN", "SG")
OPENCC_CONVERTER = OpenCC("t2s") if OpenCC else None


def preferred_display_title(
    title: str,
    original_title: str,
    original_language: str,
    alternative_titles: Sequence[dict[str, str]],
    translations: Sequence[dict[str, str]],
) -> tuple[str, str]:
    original = preferred_native_chinese_title(original_title, original_language)
    if original:
        return original
    if is_localized_chinese_primary_title(title, original_title, original_language):
        return title, "primary"
    preferred = preferred_chinese_title(alternative_titles)
    if preferred:
        return preferred, "alternative_titles"
    preferred = preferred_chinese_title(translations)
    if preferred:
        return preferred, "translations"
    if is_chinese(title):
        simplified = to_simplified_chinese(title)
        return simplified or title, "primary_simplified" if simplified != title else "primary"
    return title, "primary"


def preferred_native_chinese_title(original_title: str, original_language: str) -> tuple[str, str] | None:
    if not original_title or not is_chinese(original_title) or not is_chinese_original_language(original_language):
        return None
    simplified = to_simplified_chinese(original_title)
    source = "original_title"
    if simplified != original_title:
        source = "original_title_simplified"
    return simplified or original_title, source


def is_localized_chinese_primary_title(title: str, original_title: str, original_language: str) -> bool:
    if not title or not is_chinese(title) or is_traditional_chinese(title):
        return False
    return is_chinese_original_language(original_language) or title != original_title


def is_chinese_original_language(value: str) -> bool:
    return value.casefold() in CHINESE_ORIGINAL_LANGUAGES


def preferred_chinese_title(values: Sequence[dict[str, str]]) -> str | None:
    for preferred_region in PREFERRED_CHINESE_REGIONS:
        for value in values:
            title = value.get("title")
            if value.get("iso_3166_1") == preferred_region and title and is_chinese(title):
                return to_simplified_chinese(title)
    return None


def titles_to_metadata(values: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    return [dict(value) for value in values]


def unique_titles(values: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict[str, str]] = []
    for value in values:
        key = (
            value.get("title", ""),
            value.get("iso_3166_1", ""),
            value.get("iso_639_1", ""),
        )
        if key not in seen:
            seen.add(key)
            result.append(dict(value))
    return result


def is_chinese(value: str | None) -> bool:
    return bool(value and CHINESE_CHARACTER_PATTERN.search(value))


def to_simplified_chinese(value: str | None) -> str | None:
    if not value or OPENCC_CONVERTER is None:
        return value
    return OPENCC_CONVERTER.convert(value)


def is_traditional_chinese(value: str | None) -> bool:
    if not value or not is_chinese(value):
        return False
    simplified = to_simplified_chinese(value)
    return bool(simplified and simplified != value)
