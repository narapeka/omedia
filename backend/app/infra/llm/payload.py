from __future__ import annotations

import json
import re
from typing import Any

from app.core.error import MatchError
from app.domain.match import HintSource, MatchHint, TitleHint, TitleKind


def hint_from_payload(payload: dict[str, Any]) -> MatchHint:
    titles: list[TitleHint] = []
    chinese_title = text(payload.get("chinese_title"))
    if chinese_title:
        titles.append(TitleHint(chinese_title, TitleKind.CHINESE, HintSource.LLM))
    english_title = text(payload.get("english_title"))
    if english_title:
        titles.append(TitleHint(english_title, TitleKind.ENGLISH, HintSource.LLM))
    return MatchHint(
        titles=tuple(titles),
        year=_optional_four_digit_year(payload.get("year")),
        tmdb_id=_optional_int(payload.get("tmdb_id")),
    )


def first_object(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        if isinstance(payload.get("items"), list) and payload["items"]:
            first = payload["items"][0]
            return first if isinstance(first, dict) else {}
        return payload
    if payload and isinstance(payload[0], dict):
        return payload[0]
    return {}


def objects(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        raw_items = payload
    else:
        raw_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    return [item for item in raw_items if isinstance(item, dict)]


def text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def loads_json_from_content(content: str) -> dict[str, Any] | list[Any]:
    text = _strip_code_fence(content.strip())
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        loaded = _loads_embedded_json(text)
    if isinstance(loaded, (dict, list)):
        return loaded
    raise MatchError("LLM returned JSON that is not an object or array")


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_four_digit_year(value: Any) -> int | None:
    year = _optional_int(value)
    if year is None:
        return None
    return year if 1900 <= year <= 2099 else None


def _strip_code_fence(text: str) -> str:
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else text


def _loads_embedded_json(text: str) -> dict[str, Any] | list[Any]:
    spans = []
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer) + 1
        if start >= 0 and end > start:
            spans.append((start, text[start:end]))
    for _start, snippet in sorted(spans, key=lambda item: item[0]):
        try:
            loaded = json.loads(snippet)
        except json.JSONDecodeError:
            continue
        if isinstance(loaded, (dict, list)):
            return loaded
    raise MatchError("LLM returned non-JSON content") from None
