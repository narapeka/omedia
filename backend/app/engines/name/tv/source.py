from __future__ import annotations

import re

from app.core.path import render_tag_suffix
from app.domain.tv import TVTagSuffix
from app.engines.name.tv.pattern import find_season, find_season_episode, has_positive_season, has_positive_season_zero


def extract_last_tag(folder_name: str) -> TVTagSuffix | None:
    matches = re.findall(r"#([^#]+)#", folder_name)
    if not matches:
        return None
    raw = matches[-1]
    return TVTagSuffix(raw_tag=raw, rendered_suffix=render_tag_suffix(raw))


def extract_season_number(text: str, fallback: int | None = 1, *, mode: str = "file") -> int | None:
    match = find_season_episode(text) or find_season(text)
    if match is None or match.season is None:
        return fallback
    if 1900 <= match.season <= 2099:
        return fallback
    return match.season


def valid_season(value: int | None, *, allow_zero: bool = True) -> int | None:
    if value is None:
        return None
    try:
        season = int(value)
    except (TypeError, ValueError):
        return None
    if season < 0:
        return None
    if season == 0 and not allow_zero:
        return None
    return season


def has_explicit_file_season(filename: str) -> bool:
    return has_positive_season(filename)


def has_explicit_season_zero(filename: str) -> bool:
    return has_positive_season_zero(filename)


def explicit_folder_season(folder_name: str) -> int | None:
    folder_season = valid_season(extract_season_number(folder_name, fallback=None, mode="folder"))
    if folder_season is not None:
        return folder_season
    return None
