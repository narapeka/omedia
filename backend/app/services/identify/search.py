from __future__ import annotations

from dataclasses import dataclass

from app.core.error import MatchError
from app.domain.media import MediaType
from app.domain.match import ConfidenceLevel, TMDBCandidate, TMDBSearchResult
from app.engines.match.manual import (
    ManualQueryKind,
    ManualRank,
    parse_manual_query,
    rank_exact_id_result,
    rank_title_result,
    sort_ranked_results,
)


@dataclass(frozen=True)
class ManualTMDBSearchResult:
    tmdb_id: int
    media_type: MediaType
    title: str
    original_title: str | None
    year: int | None
    overview: str | None
    poster_url: str | None
    vote_average: float | None
    popularity: float | None
    origin_country: tuple[str, ...]
    directors: tuple[str, ...]
    cast: tuple[str, ...]
    confidence: ConfidenceLevel
    score: int
    reason: str


@dataclass(frozen=True)
class ManualTMDBSearchPage:
    results: tuple[ManualTMDBSearchResult, ...]
    page: int = 1
    total_pages: int = 0
    total_results: int = 0


@dataclass(frozen=True)
class _RankedCandidate:
    candidate: TMDBCandidate
    rank: ManualRank


class ManualTMDBSearchService:
    def __init__(self, tmdb_client):
        self.tmdb_client = tmdb_client

    def search(
        self,
        *,
        media_type: MediaType,
        query: str | None = None,
        year: int | None = None,
        language: str = "zh-CN",
        page: int = 1,
        fallback_title: str | None = None,
        fallback_year: int | None = None,
    ) -> ManualTMDBSearchPage:
        page = max(1, int(page or 1))
        parsed = parse_manual_query(query)
        title_query = _explicit_title_query(parsed)
        using_fallback_title = False
        if title_query is None and parsed is None:
            title_query = _fallback_title(fallback_title)
            using_fallback_title = title_query is not None
        requested_year = year if year is not None else (fallback_year if using_fallback_title else None)
        if parsed is None and not title_query:
            raise MatchError(
                "Manual TMDB search requires a query or candidate group context",
                code="identify.search_context_required",
            )

        ranked: list[_RankedCandidate] = []
        seen_ids: set[int] = set()
        for candidate in self._exact_candidates(parsed, media_type):
            if candidate.media_type != media_type or candidate.tmdb_id in seen_ids:
                continue
            seen_ids.add(candidate.tmdb_id)
            ranked.append(_RankedCandidate(candidate, rank_exact_id_result(candidate)))

        search_page = None
        if title_query:
            search_page = self.tmdb_client.search_page(media_type, title_query, requested_year, language, page)
            for search_result in search_page.results:
                if search_result.media_type != media_type or search_result.tmdb_id in seen_ids:
                    continue
                candidate = self._load_search_result_details(media_type, search_result, language)
                if candidate.media_type != media_type or candidate.tmdb_id in seen_ids:
                    continue
                seen_ids.add(candidate.tmdb_id)
                ranked.append(
                    _RankedCandidate(
                        candidate,
                        rank_title_result(
                            candidate,
                            requested_title=title_query,
                            requested_year=requested_year,
                        ),
                    )
                )

        ordered = sort_ranked_results(ranked)
        return ManualTMDBSearchPage(
            results=tuple(_search_result(item.candidate, item.rank) for item in ordered),
            page=search_page.page if search_page is not None else page,
            total_pages=search_page.total_pages if search_page is not None else (1 if ordered else 0),
            total_results=search_page.total_results if search_page is not None else len(ordered),
        )

    def _exact_candidates(
        self,
        parsed,
        media_type: MediaType,
    ) -> list[TMDBCandidate]:
        if parsed is None:
            return []
        if parsed.kind == ManualQueryKind.TMDB_ID:
            if parsed.media_type_hint is not None and parsed.media_type_hint != media_type:
                return []
            candidate = self.tmdb_client.get_by_id(media_type, int(parsed.tmdb_id or 0))
            return [candidate] if candidate is not None else []
        if parsed.kind == ManualQueryKind.IMDB_ID:
            finder = getattr(self.tmdb_client, "find_by_external_id", None)
            if finder is None:
                return []
            candidate = finder(parsed.imdb_id, media_type)
            return [candidate] if candidate is not None else []
        return []

    def _load_search_result_details(
        self,
        media_type: MediaType,
        search_result: TMDBSearchResult,
        language: str,
    ) -> TMDBCandidate:
        loader = getattr(self.tmdb_client, "load_candidate_details", None)
        if loader is None:
            return search_result.to_candidate()
        try:
            candidate = loader(media_type, search_result.tmdb_id, language, search_result)
        except MatchError:
            return search_result.to_candidate()
        return candidate if isinstance(candidate, TMDBCandidate) else search_result.to_candidate()


def _explicit_title_query(parsed) -> str | None:
    if parsed is not None and parsed.kind == ManualQueryKind.TITLE and parsed.title:
        return parsed.title
    return None


def _fallback_title(fallback_title: str | None) -> str | None:
    fallback = (fallback_title or "").strip()
    return fallback or None


def _search_result(candidate: TMDBCandidate, rank: ManualRank) -> ManualTMDBSearchResult:
    metadata = candidate.metadata
    return ManualTMDBSearchResult(
        tmdb_id=candidate.tmdb_id,
        media_type=candidate.media_type,
        title=candidate.title,
        original_title=candidate.original_title,
        year=candidate.year,
        overview=_optional_str(metadata.get("overview")),
        poster_url=_optional_str(metadata.get("poster_url")),
        vote_average=_optional_float(metadata.get("vote_average")),
        popularity=_optional_float(metadata.get("popularity")),
        origin_country=tuple(_string_list(metadata.get("origin_country"))),
        directors=tuple(_string_list(metadata.get("directors"))),
        cast=tuple(_string_list(metadata.get("cast"))),
        confidence=rank.confidence,
        score=rank.score,
        reason=rank.reason,
    )


def _optional_str(value: object) -> str | None:
    return str(value) if value not in (None, "") else None


def _optional_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if item not in (None, "")]
