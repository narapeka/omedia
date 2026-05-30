from __future__ import annotations

import re
from typing import Any

from app.domain.media import MediaType
from app.domain.media import MediaCandidate, MediaExtensionPolicy
from app.domain.match import HintSource, MatchHint, TitleHint, TitleKind
from app.engines.match.context import derive_match_context
from app.engines.name.movie.source import extract_movie_source_name


class HintExtractor:
    """Deterministic source-name extraction used before optional LLM assistance."""

    def __init__(self, extensions: MediaExtensionPolicy):
        self.extensions = extensions

    def extract(self, candidate: MediaCandidate) -> MatchHint:
        tmdb_id = _extract_tmdb_id(candidate.display_name)
        if candidate.media_type == MediaType.MOVIE:
            title, year, _tag = extract_movie_source_name(candidate.candidate_path, extensions=self.extensions)
            return MatchHint(titles=_title_hints(title), year=year, tmdb_id=tmdb_id)

        context = derive_match_context(candidate, self.extensions)
        if context.tv is not None:
            title = context.tv.show_title_source
            year = _extract_title_and_year(candidate.display_name)[1]
            return MatchHint(titles=_title_hints(title), year=year, tmdb_id=tmdb_id, context=context)

        title, year = _extract_title_and_year(candidate.display_name)
        return MatchHint(titles=_title_hints(title), year=year, tmdb_id=tmdb_id)


def _title_hints(title: str | None) -> tuple[TitleHint, ...]:
    if not title:
        return ()
    return (TitleHint(title, TitleKind.SOURCE, HintSource.DETERMINISTIC),)


def _extract_title_and_year(value: str) -> tuple[str, int | None]:
    cleaned = re.sub(r"#[^#]+#", " ", value)
    cleaned = re.sub(r"\{?\btmdb[-_ ]?\d+\}?", " ", cleaned, flags=re.IGNORECASE)
    year_match = re.search(r"\b((?:19|20)\d{2})\b", cleaned)
    year = _optional_int(year_match.group(1) if year_match else None)
    if year:
        cleaned = re.sub(rf"[\s._([{{-]*{year}[\s._)\]}}-]*", " ", cleaned, count=1)
    cleaned = re.sub(r"[._]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or value, year


def _extract_tmdb_id(value: str) -> int | None:
    match = re.search(r"\btmdb[-_ ]?(\d+)\b", value, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
