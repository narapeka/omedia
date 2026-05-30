from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

from app.domain.match import ConfidenceLevel, YearMatch
from app.domain.media import MediaType
from app.domain.match import TMDBCandidate
from app.engines.match.confidence import classify_year_match


class ManualQueryKind(str, Enum):
    TITLE = "title"
    TMDB_ID = "tmdb_id"
    IMDB_ID = "imdb_id"


@dataclass(frozen=True)
class ManualSearchQuery:
    kind: ManualQueryKind
    raw: str
    title: str | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None
    media_type_hint: MediaType | None = None


@dataclass(frozen=True)
class ManualRank:
    score: int
    confidence: ConfidenceLevel
    reason: str


_IMDB_ID_PATTERN = re.compile(r"\btt\d{6,12}\b", re.IGNORECASE)
_TMDB_PATH_PATTERN = re.compile(r"/(movie|tv)/(\d+)(?:[/-]|$)", re.IGNORECASE)
_NON_TITLE_CHARS = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)

_EXACT_ID_SCORE = 10000
_EXACT_TITLE_YEAR_SCORE = 9000
_EXACT_TITLE_SCORE = 8000
_TITLE_YEAR_WEAK_SCORE = 6500
_PARTIAL_TITLE_SCORE = 4500
_WEAK_RESULT_SCORE = 1000


def parse_manual_query(value: str | None) -> ManualSearchQuery | None:
    raw = (value or "").strip()
    if not raw:
        return None

    tmdb_url = _parse_tmdb_url(raw)
    if tmdb_url is not None:
        media_type, tmdb_id = tmdb_url
        return ManualSearchQuery(
            kind=ManualQueryKind.TMDB_ID,
            raw=raw,
            tmdb_id=tmdb_id,
            media_type_hint=media_type,
        )

    imdb_id = _parse_imdb_id(raw)
    if imdb_id:
        return ManualSearchQuery(kind=ManualQueryKind.IMDB_ID, raw=raw, imdb_id=imdb_id)

    if raw.isdigit():
        return ManualSearchQuery(kind=ManualQueryKind.TMDB_ID, raw=raw, tmdb_id=int(raw))

    return ManualSearchQuery(kind=ManualQueryKind.TITLE, raw=raw, title=raw)


def normalize_title(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    normalized = _NON_TITLE_CHARS.sub(" ", normalized)
    return " ".join(normalized.split())


def rank_exact_id_result(candidate: TMDBCandidate) -> ManualRank:
    return ManualRank(
        score=_with_popularity_tiebreaker(_EXACT_ID_SCORE, candidate),
        confidence=ConfidenceLevel.HIGH,
        reason="exact_id_match",
    )


def rank_title_result(
    candidate: TMDBCandidate,
    *,
    requested_title: str,
    requested_year: int | None = None,
) -> ManualRank:
    title_match = _candidate_has_title(candidate, requested_title)
    partial_match = title_match or _candidate_has_partial_title(candidate, requested_title)
    year_match = classify_year_match(requested_year, candidate.year)

    if title_match and year_match == YearMatch.EXACT:
        base = _EXACT_TITLE_YEAR_SCORE
        confidence = ConfidenceLevel.HIGH
        reason = "exact_title_year_match"
    elif title_match and requested_year is None:
        base = _EXACT_TITLE_SCORE
        confidence = ConfidenceLevel.HIGH
        reason = "exact_title_match"
    elif title_match:
        base = _TITLE_YEAR_WEAK_SCORE
        confidence = ConfidenceLevel.MEDIUM
        reason = "title_match_year_weakness"
    elif partial_match:
        base = _PARTIAL_TITLE_SCORE
        confidence = ConfidenceLevel.LOW
        reason = "partial_title_match"
    else:
        base = _WEAK_RESULT_SCORE
        confidence = ConfidenceLevel.LOW
        reason = "weak_tmdb_search_result"

    return ManualRank(
        score=_with_popularity_tiebreaker(base, candidate),
        confidence=confidence,
        reason=reason,
    )


def sort_ranked_results(items):
    return sorted(
        items,
        key=lambda item: (
            item.rank.score,
            _metadata_float(item.candidate, "popularity"),
            _metadata_float(item.candidate, "vote_average"),
            -item.candidate.tmdb_id,
        ),
        reverse=True,
    )


def _parse_tmdb_url(value: str) -> tuple[MediaType, int] | None:
    parsed = urlparse(value)
    path = parsed.path if parsed.scheme or parsed.netloc else value
    match = _TMDB_PATH_PATTERN.search(path)
    if not match:
        return None
    media_type = MediaType.TV if match.group(1).casefold() == "tv" else MediaType.MOVIE
    return media_type, int(match.group(2))


def _parse_imdb_id(value: str) -> str | None:
    match = _IMDB_ID_PATTERN.search(value)
    return match.group(0).lower() if match else None


def _candidate_has_title(candidate: TMDBCandidate, requested_title: str) -> bool:
    normalized = normalize_title(requested_title)
    return bool(normalized and any(normalize_title(title) == normalized for title in candidate.known_titles()))


def _candidate_has_partial_title(candidate: TMDBCandidate, requested_title: str) -> bool:
    normalized = normalize_title(requested_title)
    if not normalized:
        return False
    for title in candidate.known_titles():
        candidate_title = normalize_title(title)
        if candidate_title and (normalized in candidate_title or candidate_title in normalized):
            return True
    return False


def _with_popularity_tiebreaker(base: int, candidate: TMDBCandidate) -> int:
    return base + min(int(round(_metadata_float(candidate, "popularity") * 10)), 99)


def _metadata_float(candidate: TMDBCandidate, key: str) -> float:
    try:
        return float(candidate.metadata.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0

