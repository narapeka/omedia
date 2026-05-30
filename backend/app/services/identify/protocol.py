from __future__ import annotations

from typing import Protocol, Sequence

from app.domain.match import MatchHint, TMDBCandidate, TMDBSearchPage, TMDBSearchResult
from app.domain.media import MediaCandidate, MediaType


class MediaNameExtractor(Protocol):
    def extract(self, candidate: MediaCandidate) -> MatchHint:
        ...


class TMDBLookupClient(Protocol):
    def get_by_id(self, media_type: MediaType, tmdb_id: int) -> TMDBCandidate | None:
        ...

    def search_page(
        self,
        media_type: MediaType,
        title: str,
        year: int | None,
        language: str,
        page: int,
    ) -> TMDBSearchPage:
        ...

    def load_candidate_details(
        self,
        media_type: MediaType,
        tmdb_id: int,
        language: str,
        fallback_search_result: TMDBSearchResult,
    ) -> TMDBCandidate | None:
        ...

    def get_tv_season_years(
        self,
        tmdb_id: int,
        season_numbers: Sequence[int],
        languages: Sequence[str],
    ) -> dict[int, int]:
        ...


class LLMHintExtractor(Protocol):
    def extract_hint(self, candidate: MediaCandidate) -> MatchHint:
        ...

    def extract_hints(
        self,
        candidates: Sequence[MediaCandidate],
        *,
        batch_size: int = 50,
    ) -> dict[str, MatchHint]:
        ...
