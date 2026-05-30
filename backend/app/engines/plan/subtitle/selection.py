from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CHINESE_MARKER_EXPRESSIONS: tuple[str, ...] = (
    "chs&eng",
    "zh&en",
    "简体&英文",
    "简英",
    "双语",
    "zh",
    "chs",
    "chi",
    "简",
    "中",
)
SUBTITLE_MARKER_TAIL_CHARS = 20


@dataclass(frozen=True)
class SubtitleCandidate:
    value: Any
    group_key: Hashable
    source_path: Path
    relative_path: Path
    extension: str


@dataclass(frozen=True)
class SubtitleSelection:
    selected: SubtitleCandidate
    ignored: tuple[SubtitleCandidate, ...]


def select_subtitle_candidates(candidates: Iterable[SubtitleCandidate]) -> list[SubtitleSelection]:
    groups: dict[Hashable, list[SubtitleCandidate]] = defaultdict(list)
    for candidate in candidates:
        groups[(candidate.group_key, candidate.extension.lower())].append(candidate)

    selections: list[SubtitleSelection] = []
    for group in groups.values():
        ordered = sorted(group, key=_stable_key)
        selected = min(ordered, key=_preference_key)
        ignored = tuple(candidate for candidate in ordered if candidate is not selected)
        selections.append(SubtitleSelection(selected=selected, ignored=ignored))
    return sorted(selections, key=lambda item: _stable_key(item.selected))


def chinese_marker_rank(path: Path) -> int | None:
    tail = _normalized_tail(path)
    for rank, expression in enumerate(CHINESE_MARKER_EXPRESSIONS):
        if _expression_matches_tail(expression, tail):
            return rank
    return None


def _preference_key(candidate: SubtitleCandidate) -> tuple[int, str]:
    rank = chinese_marker_rank(candidate.source_path)
    return (rank if rank is not None else len(CHINESE_MARKER_EXPRESSIONS), _stable_key(candidate))


def _stable_key(candidate: SubtitleCandidate) -> str:
    return candidate.relative_path.as_posix().casefold()


def _normalized_tail(path: Path) -> str:
    stem = path.stem.casefold()
    return stem[-SUBTITLE_MARKER_TAIL_CHARS:]


def _expression_matches_tail(expression: str, tail: str) -> bool:
    parts = [part.casefold() for part in expression.split("&")]
    if len(parts) == 1:
        return parts[0] in tail
    pattern = ".*?".join(re.escape(part) for part in parts)
    return re.search(pattern, tail, flags=re.IGNORECASE) is not None
