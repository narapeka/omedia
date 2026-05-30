from __future__ import annotations

from typing import Protocol, Sequence

from app.domain.media import MediaType
from app.domain.cache import TMDBDetailCache
from app.domain.match import TMDBCandidate, TMDBSearchPage, TMDBSearchResult
from app.domain.tv import TVEpisodeCatalog
from app.infra.tmdb.entry import candidate_from_cache, candidate_to_cache
from app.infra.tmdb.ttl import (
    DEFAULT_TMDB_CACHE_MAX_ENTRIES,
    DEFAULT_TMDB_CACHE_TTL_SECONDS,
    MISSING,
    TMDBCacheStats,
    TTLCache,
)


class TMDBLookupProvider(Protocol):
    def get_by_id(self, media_type: MediaType, tmdb_id: int) -> TMDBCandidate | None:
        ...

    def find_by_external_id(self, imdb_id: str, media_type: MediaType) -> TMDBCandidate | None:
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

    def get_tv_episode_titles(
        self,
        tmdb_id: int,
        season_numbers: Sequence[int],
        languages: Sequence[str],
    ) -> dict[int, dict[int, str]]:
        ...

    def get_tv_season_years(
        self,
        tmdb_id: int,
        season_numbers: Sequence[int],
        languages: Sequence[str],
    ) -> dict[int, int]:
        ...

    def get_tv_episode_catalog(
        self,
        tmdb_id: int,
        languages: Sequence[str],
    ) -> TVEpisodeCatalog:
        ...


class TMDBMetadataService:
    """Read-through TMDB detail cache plus in-process caches for volatile lookups."""

    def __init__(
        self,
        provider: TMDBLookupProvider,
        *,
        ttl_seconds: float = DEFAULT_TMDB_CACHE_TTL_SECONDS,
        max_entries: int = DEFAULT_TMDB_CACHE_MAX_ENTRIES,
        store=None,
        search_cache: TTLCache | None = None,
        detail_cache: TTLCache | None = None,
        episode_title_cache: TTLCache | None = None,
        episode_catalog_cache: TTLCache | None = None,
        season_year_cache: TTLCache | None = None,
    ):
        self.provider = provider
        self.store = store
        self.search_cache = search_cache or TTLCache(ttl_seconds=ttl_seconds, max_entries=max_entries)
        self.detail_cache = detail_cache or TTLCache(ttl_seconds=ttl_seconds, max_entries=max_entries)
        self.episode_title_cache = episode_title_cache or TTLCache(ttl_seconds=ttl_seconds, max_entries=max_entries)
        self.episode_catalog_cache = episode_catalog_cache or TTLCache(ttl_seconds=ttl_seconds, max_entries=max_entries)
        self.season_year_cache = season_year_cache or TTLCache(ttl_seconds=ttl_seconds, max_entries=max_entries)

    def get_by_id(self, media_type: MediaType, tmdb_id: int) -> TMDBCandidate | None:
        normalized_id = int(tmdb_id)
        if self.store is not None:
            cached = self.store.get_tmdb_detail(media_type.value, normalized_id)
            if cached is not None:
                candidate = candidate_from_cache(cached, media_type, normalized_id)
                if candidate is not None:
                    return candidate
        candidate = self.provider.get_by_id(media_type, normalized_id)
        if candidate is not None and self.store is not None:
            self.store.save_tmdb_detail(
                TMDBDetailCache(
                    media_type=media_type.value,
                    tmdb_id=normalized_id,
                    metadata=candidate_to_cache(candidate),
                )
            )
        return candidate

    def find_by_external_id(self, imdb_id: str, media_type: MediaType) -> TMDBCandidate | None:
        normalized_id = str(imdb_id).strip().lower()
        if not normalized_id:
            return None
        key = ("external_id", media_type.value, normalized_id)
        candidate = self.search_cache.get_or_set(
            key,
            lambda: self.provider.find_by_external_id(normalized_id, media_type),
        )
        if not isinstance(candidate, TMDBCandidate):
            return None
        if candidate.media_type != media_type:
            return None
        if self.store is not None:
            self.store.save_tmdb_detail(
                TMDBDetailCache(
                    media_type=media_type.value,
                    tmdb_id=int(candidate.tmdb_id),
                    metadata=candidate_to_cache(candidate),
                )
            )
        return candidate

    def search_page(
        self,
        media_type: MediaType,
        title: str,
        year: int | None,
        language: str,
        page: int,
    ) -> TMDBSearchPage:
        key = ("search_page", media_type.value, _normalize_search_title(title), year, language, int(page))
        result = self.search_cache.get_or_set(
            key,
            lambda: self.provider.search_page(media_type, title, year, language, page),
        )
        if not isinstance(result, TMDBSearchPage):
            return TMDBSearchPage()
        return TMDBSearchPage(
            results=tuple(result.results),
            page=result.page,
            total_pages=result.total_pages,
            total_results=result.total_results,
        )

    def load_candidate_details(
        self,
        media_type: MediaType,
        tmdb_id: int,
        language: str,
        fallback_search_result: TMDBSearchResult,
    ) -> TMDBCandidate | None:
        normalized_id = int(tmdb_id)
        key = ("search_detail", media_type.value, normalized_id, language)
        candidate = self.detail_cache.get_or_set(
            key,
            lambda: self.provider.load_candidate_details(
                media_type,
                normalized_id,
                language,
                fallback_search_result,
            ),
        )
        if not isinstance(candidate, TMDBCandidate):
            return fallback_search_result.to_candidate()
        if candidate.media_type != media_type or int(candidate.tmdb_id) != normalized_id:
            return fallback_search_result.to_candidate()
        return candidate

    def get_tv_episode_titles(
        self,
        tmdb_id: int,
        season_numbers: Sequence[int],
        languages: Sequence[str],
    ) -> dict[int, dict[int, str]]:
        language_key = tuple(languages)
        results: dict[int, dict[int, str]] = {}
        for season_number in _season_key(season_numbers):
            key = ("episode_titles", int(tmdb_id), season_number, language_key)
            cached = self.episode_title_cache.get(key)
            if cached is MISSING:
                fetched = self.provider.get_tv_episode_titles(tmdb_id, [season_number], languages)
                cached = dict(fetched.get(season_number, {}))
                self.episode_title_cache.set(key, cached)
            results[season_number] = dict(cached)
        return results

    def get_tv_season_years(
        self,
        tmdb_id: int,
        season_numbers: Sequence[int],
        languages: Sequence[str],
    ) -> dict[int, int]:
        language_key = tuple(languages)
        results: dict[int, int] = {}
        for season_number in _season_key(season_numbers):
            key = ("season_years", int(tmdb_id), season_number, language_key)
            cached = self.season_year_cache.get(key)
            if cached is MISSING:
                fetched = self.provider.get_tv_season_years(tmdb_id, [season_number], languages)
                cached = fetched.get(season_number)
                self.season_year_cache.set(key, cached)
            if cached is not None:
                results[season_number] = int(cached)
        return results

    def get_tv_episode_catalog(
        self,
        tmdb_id: int,
        languages: Sequence[str],
    ) -> TVEpisodeCatalog:
        language_key = tuple(languages)
        key = ("episode_catalog", int(tmdb_id), language_key)
        cached = self.episode_catalog_cache.get(key)
        if cached is MISSING:
            cached = self.provider.get_tv_episode_catalog(tmdb_id, languages)
            if not isinstance(cached, TVEpisodeCatalog):
                cached = TVEpisodeCatalog.empty()
            self.episode_catalog_cache.set(key, cached)
            for season_number, titles in cached.seasons.items():
                self.episode_title_cache.set(
                    ("episode_titles", int(tmdb_id), int(season_number), language_key),
                    dict(titles),
                )
        return TVEpisodeCatalog({season: dict(titles) for season, titles in cached.seasons.items()})

    def clear_cache(self) -> int:
        deleted = self.store.clear_tmdb_details() if self.store is not None else 0
        self.search_cache.clear()
        self.detail_cache.clear()
        self.episode_title_cache.clear()
        self.episode_catalog_cache.clear()
        self.season_year_cache.clear()
        return deleted

    def cache_stats(self) -> TMDBCacheStats:
        stats = [
            self.search_cache.stats(),
            self.detail_cache.stats(),
            self.episode_title_cache.stats(),
            self.episode_catalog_cache.stats(),
            self.season_year_cache.stats(),
        ]
        return TMDBCacheStats(
            hits=sum(item.hits for item in stats),
            misses=sum(item.misses for item in stats),
            entries=sum(item.entries for item in stats),
        )


def _normalize_search_title(title: str) -> str:
    return " ".join(title.casefold().split())


def _season_key(season_numbers: Sequence[int]) -> tuple[int, ...]:
    return tuple(sorted({int(value) for value in season_numbers}))
