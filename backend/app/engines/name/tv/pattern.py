from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class TVPatternKind(str, Enum):
    SEASON = "season"
    EPISODE = "episode"
    SEASON_EPISODE = "season_episode"
    RANGE = "range"


@dataclass(frozen=True)
class TVPatternMatch:
    kind: TVPatternKind
    season: int | None = None
    episode: int | None = None
    end_episode: int | None = None
    token: str = ""


@dataclass(frozen=True)
class _RangePattern:
    pattern: re.Pattern[str]
    shape: str


CHINESE_NUMERALS = {
    "\u96f6": 0,
    "\u3007": 0,
    "\u4e00": 1,
    "\u58f9": 1,
    "\u4e8c": 2,
    "\u4e24": 2,
    "\u8d30": 2,
    "\u4e09": 3,
    "\u53c1": 3,
    "\u56db": 4,
    "\u8086": 4,
    "\u4e94": 5,
    "\u4f0d": 5,
    "\u516d": 6,
    "\u9646": 6,
    "\u4e03": 7,
    "\u67d2": 7,
    "\u516b": 8,
    "\u634c": 8,
    "\u4e5d": 9,
    "\u7396": 9,
    "\u5341": 10,
    "\u62fe": 10,
    "\u767e": 100,
    "\u4f70": 100,
    "\u5343": 1000,
    "\u4edf": 1000,
}

_CHINESE_NUMBER = "".join(CHINESE_NUMERALS)
_NUMBER_TOKEN = rf"[{_CHINESE_NUMBER}\d]+"
_BOUNDARY = r"(?<![A-Za-z0-9])"
_END_BOUNDARY = r"(?![A-Za-z0-9])"
_RANGE_SEPARATOR = r"(?:-|~|\u2013|\u2014|\u81f3|\u5230)"
_EPISODE_WORD = r"(?:Episodes?|[Ee][Pp]?)"
_CHINESE_EPISODE_UNIT = r"\u96c6"
_RANGE_SEASON_TO_SEASON = "season_to_season"
_RANGE_SAME_SEASON = "same_season"
_RANGE_EPISODE_ONLY = "episode_only"

SEASON_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(rf"{_BOUNDARY}[Ss](?:eason[.\s_-]*)?(\d+)(?=[EePp]|\b|[.\s_-])", re.IGNORECASE),
    re.compile(rf"{_BOUNDARY}Season[.\s_-]*(\d+){_END_BOUNDARY}", re.IGNORECASE),
    re.compile(rf"\u7b2c({_NUMBER_TOKEN})\u5b63", re.IGNORECASE),
)

SEASON_EPISODE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(rf"{_BOUNDARY}[Ss][.\s_-]*(\d+)[.\s_-]*[Ee][Pp]?[.\s_-]*(\d+){_END_BOUNDARY}", re.IGNORECASE),
    re.compile(rf"{_BOUNDARY}(\d+)[xX](\d+){_END_BOUNDARY}", re.IGNORECASE),
    re.compile(
        rf"{_BOUNDARY}Season[.\s_-]*(\d+)[.\s_-]+{_EPISODE_WORD}[.\s_-]*(\d+){_END_BOUNDARY}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\u7b2c({_NUMBER_TOKEN})\s*\u5b63\s*\u7b2c({_NUMBER_TOKEN})\s*{_CHINESE_EPISODE_UNIT}",
        re.IGNORECASE,
    ),
)

EPISODE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(rf"{_BOUNDARY}[Ee][Pp][.\s_-]*(\d+){_END_BOUNDARY}", re.IGNORECASE),
    re.compile(rf"{_BOUNDARY}[Ee](?:pisode)?[.\s_-]*(\d+){_END_BOUNDARY}", re.IGNORECASE),
    re.compile(rf"\u7b2c({_NUMBER_TOKEN})\u96c6", re.IGNORECASE),
)

RANGE_PATTERNS: tuple[_RangePattern, ...] = (
    _RangePattern(
        re.compile(
            rf"{_BOUNDARY}[Ss][.\s_-]*(\d+)[.\s_-]*[Ee][Pp]?[.\s_-]*(\d+)"
            rf"\s*{_RANGE_SEPARATOR}\s*[Ss][.\s_-]*(\d+)[.\s_-]*[Ee][Pp]?[.\s_-]*(\d+){_END_BOUNDARY}",
            re.IGNORECASE,
        ),
        _RANGE_SEASON_TO_SEASON,
    ),
    _RangePattern(
        re.compile(
            rf"{_BOUNDARY}[Ss][.\s_-]*(\d+)[.\s_-]*[Ee][Pp]?[.\s_-]*(\d+)"
            rf"\s*{_RANGE_SEPARATOR}\s*[Ee][Pp]?[.\s_-]*(\d+){_END_BOUNDARY}",
            re.IGNORECASE,
        ),
        _RANGE_SAME_SEASON,
    ),
    _RangePattern(
        re.compile(
            rf"{_BOUNDARY}(\d+)[xX](\d+)\s*{_RANGE_SEPARATOR}\s*(\d+)[xX](\d+){_END_BOUNDARY}",
            re.IGNORECASE,
        ),
        _RANGE_SEASON_TO_SEASON,
    ),
    _RangePattern(
        re.compile(
            rf"{_BOUNDARY}[Ss][.\s_-]*(\d+)[.\s_-]*[Ee][Pp]?[.\s_-]*(\d+)[.\s_-]*[Ee][Pp]?[.\s_-]*(\d+){_END_BOUNDARY}",
            re.IGNORECASE,
        ),
        _RANGE_SAME_SEASON,
    ),
    _RangePattern(
        re.compile(
            rf"{_BOUNDARY}Season[.\s_-]*(\d+)[.\s_-]+{_EPISODE_WORD}[.\s_-]*(\d+)"
            rf"\s*{_RANGE_SEPARATOR}\s*(?:{_EPISODE_WORD}[.\s_-]*)?(\d+){_END_BOUNDARY}",
            re.IGNORECASE,
        ),
        _RANGE_SAME_SEASON,
    ),
    _RangePattern(
        re.compile(
            rf"\u7b2c({_NUMBER_TOKEN})\s*\u5b63\s*\u7b2c({_NUMBER_TOKEN})\s*{_CHINESE_EPISODE_UNIT}?"
            rf"\s*{_RANGE_SEPARATOR}\s*(?:\u7b2c)?({_NUMBER_TOKEN})\s*{_CHINESE_EPISODE_UNIT}",
            re.IGNORECASE,
        ),
        _RANGE_SAME_SEASON,
    ),
    _RangePattern(
        re.compile(
            rf"{_BOUNDARY}[Ee][Pp]?[.\s_-]*(\d+)[.\s_-]*[Ee][Pp]?[.\s_-]*(\d+){_END_BOUNDARY}",
            re.IGNORECASE,
        ),
        _RANGE_EPISODE_ONLY,
    ),
    _RangePattern(
        re.compile(
            rf"{_BOUNDARY}{_EPISODE_WORD}[.\s_-]*(\d+)\s*{_RANGE_SEPARATOR}\s*(?:{_EPISODE_WORD}[.\s_-]*)?(\d+){_END_BOUNDARY}",
            re.IGNORECASE,
        ),
        _RANGE_EPISODE_ONLY,
    ),
    _RangePattern(
        re.compile(
            rf"\u7b2c({_NUMBER_TOKEN})\s*{_CHINESE_EPISODE_UNIT}?\s*{_RANGE_SEPARATOR}\s*"
            rf"(?:\u7b2c)?({_NUMBER_TOKEN})\s*{_CHINESE_EPISODE_UNIT}",
            re.IGNORECASE,
        ),
        _RANGE_EPISODE_ONLY,
    ),
)


def normalize_pattern_text(text: str) -> str:
    value = _to_half_width_digits(text)
    value = re.sub(r"[\[\]{}()\u3010\u3011]", " ", value)
    value = re.sub(r"[._]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_chinese_number(text: str) -> int:
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    arabic = re.search(r"\d+", text)
    if arabic:
        return int(arabic.group())
    return _parse_chinese_integer(text)


def find_range(text: str) -> TVPatternMatch | None:
    normalized = normalize_pattern_text(text)
    for range_pattern in RANGE_PATTERNS:
        match = range_pattern.pattern.search(normalized)
        if not match:
            continue
        values = [_parse_number_token(item) for item in match.groups()]
        if range_pattern.shape == _RANGE_SEASON_TO_SEASON:
            if values[0] != values[2] or values[3] <= values[1]:
                continue
            return _valid_match(
                TVPatternKind.RANGE,
                season=values[0],
                episode=values[1],
                end_episode=values[3],
                token=match.group(0),
            )
        if range_pattern.shape == _RANGE_SAME_SEASON:
            if values[2] <= values[1]:
                continue
            return _valid_match(
                TVPatternKind.RANGE,
                season=values[0],
                episode=values[1],
                end_episode=values[2],
                token=match.group(0),
            )
        if range_pattern.shape != _RANGE_EPISODE_ONLY:
            continue
        if values[1] <= values[0]:
            continue
        return _valid_match(
            TVPatternKind.RANGE,
            episode=values[0],
            end_episode=values[1],
            token=match.group(0),
        )
    return None


def find_season_episode(text: str) -> TVPatternMatch | None:
    normalized = normalize_pattern_text(text)
    for pattern in SEASON_EPISODE_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        return _valid_match(
            TVPatternKind.SEASON_EPISODE,
            season=_parse_number_token(match.group(1)),
            episode=_parse_number_token(match.group(2)),
            token=match.group(0),
        )
    return None


def find_episode(text: str) -> TVPatternMatch | None:
    normalized = normalize_pattern_text(text)
    for pattern in EPISODE_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        episode = _parse_number_token(match.group(1))
        return _valid_match(TVPatternKind.EPISODE, episode=episode, token=match.group(0))
    return None


def find_season(text: str) -> TVPatternMatch | None:
    normalized = normalize_pattern_text(text)
    normalized = re.sub(r"(?:\u5168|\u5171|\u603b)?\d+\u96c6", " ", normalized)
    for pattern in SEASON_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        season = _parse_number_token(match.group(1))
        return _valid_match(TVPatternKind.SEASON, season=season, token=match.group(0))
    return None


def has_positive_season(text: str) -> bool:
    return find_season(text) is not None or find_season_episode(text) is not None


def has_positive_season_zero(text: str) -> bool:
    season = find_season(text) or find_season_episode(text)
    return bool(season and season.season == 0)


def _parse_number_token(token: str) -> int:
    return parse_chinese_number(token) if re.search(f"[{_CHINESE_NUMBER}]", token) else int(token)


def _parse_chinese_integer(text: str) -> int:
    total = 0
    section = 0
    for char in text:
        value = CHINESE_NUMERALS.get(char)
        if value is None:
            continue
        if value >= 10:
            section = (section or 1) * value
            total += section
            section = 0
        else:
            section = value
    return total + section


def _valid_match(
    kind: TVPatternKind,
    *,
    season: int | None = None,
    episode: int | None = None,
    end_episode: int | None = None,
    token: str,
) -> TVPatternMatch | None:
    if season is not None and season < 0:
        return None
    if episode is not None and episode < 1:
        return None
    if end_episode is not None and end_episode < 1:
        return None
    return TVPatternMatch(kind, season=season, episode=episode, end_episode=end_episode, token=token)


def _to_half_width_digits(value: str) -> str:
    return value.translate(str.maketrans("\uff10\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19", "0123456789"))
