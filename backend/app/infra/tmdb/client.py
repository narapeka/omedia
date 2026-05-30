from __future__ import annotations

import json
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from app.core.error import MatchError
from app.domain.match import TMDBCandidate, TMDBSearchPage, TMDBSearchResult
from app.domain.media import MediaType
from app.domain.tv import TVEpisodeCatalog
from app.infra.http.requester import ProviderRequester, RequesterPolicy
from app.infra.tmdb.payload import (
    candidate_from_detail,
    looks_like_bearer_token,
    optional_int,
    search_params,
    search_result_from_payload,
    tmdb_namespace,
    year_from_date,
)

TMDB_REQUESTER_POLICY = RequesterPolicy(
    retry_statuses=frozenset({429, 500, 502, 503, 504}),
    max_retries=3,
    backoff_initial_seconds=1.0,
    backoff_max_seconds=30.0,
    max_concurrency=4,
)


class TMDBHttpClient:
    """Small TMDB v3 HTTP client for match and TV episode titles."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.themoviedb.org/3",
        timeout_seconds: float = 15.0,
        rate_limit: float = 5.0,
        proxy: str | None = None,
        requester: ProviderRequester | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.requester = requester or ProviderRequester(
            name="tmdb",
            rate_limit=rate_limit,
            proxy=proxy,
            policy=TMDB_REQUESTER_POLICY,
        )

    def get_by_id(self, media_type: MediaType, tmdb_id: int) -> TMDBCandidate | None:
        namespace = tmdb_namespace(media_type)
        payload = self._get(
            f"/{namespace}/{tmdb_id}",
            {
                "language": "zh-CN",
                "append_to_response": "alternative_titles,translations,external_ids,credits",
            },
        )
        if not payload:
            return None
        return candidate_from_detail(media_type, payload)

    def find_by_external_id(self, imdb_id: str, media_type: MediaType) -> TMDBCandidate | None:
        payload = self._get(
            f"/find/{imdb_id}",
            {
                "external_source": "imdb_id",
                "language": "zh-CN",
            },
            swallow_404=True,
        )
        namespace = f"{tmdb_namespace(media_type)}_results"
        for item in payload.get(namespace) or []:
            tmdb_id = item.get("id")
            if isinstance(tmdb_id, int):
                return self.get_by_id(media_type, tmdb_id)
        return None

    def search_page(
        self,
        media_type: MediaType,
        title: str,
        year: int | None,
        language: str,
        page: int,
    ) -> TMDBSearchPage:
        namespace = tmdb_namespace(media_type)
        endpoint = f"/search/{namespace}"
        seen: set[int] = set()
        results: list[TMDBSearchResult] = []
        payload = self._get(endpoint, search_params(media_type, title, year, language, page))
        for item in payload.get("results") or []:
            tmdb_id = item.get("id")
            if not isinstance(tmdb_id, int) or tmdb_id in seen:
                continue
            result = search_result_from_payload(media_type, item)
            if result is None:
                continue
            seen.add(tmdb_id)
            results.append(result)
        return TMDBSearchPage(
            results=tuple(results),
            page=optional_int(payload.get("page")) or page,
            total_pages=max(optional_int(payload.get("total_pages")) or 0, 0),
            total_results=max(optional_int(payload.get("total_results")) or 0, 0),
        )

    def load_candidate_details(
        self,
        media_type: MediaType,
        tmdb_id: int,
        language: str,
        fallback_search_result: TMDBSearchResult,
    ) -> TMDBCandidate | None:
        namespace = tmdb_namespace(media_type)
        payload = self._get(
            f"/{namespace}/{int(tmdb_id)}",
            {
                "language": language,
                "append_to_response": "alternative_titles,translations,external_ids,credits",
            },
            swallow_404=True,
        )
        if not payload:
            return fallback_search_result.to_candidate()
        candidate = candidate_from_detail(media_type, payload)
        return candidate if candidate.tmdb_id else fallback_search_result.to_candidate()

    def get_tv_episode_titles(
        self,
        tmdb_id: int,
        season_numbers: Sequence[int],
        languages: Sequence[str],
    ) -> dict[int, dict[int, str]]:
        titles: dict[int, dict[int, str]] = {}
        for season_number in sorted(set(season_numbers)):
            for language in languages:
                payload = self._get(
                    f"/tv/{tmdb_id}/season/{season_number}",
                    {"language": language},
                    swallow_404=True,
                )
                episodes = payload.get("episodes") if payload else None
                if not episodes:
                    continue
                titles[season_number] = {
                    int(item["episode_number"]): str(item["name"])
                    for item in episodes
                    if item.get("episode_number") is not None and item.get("name")
                }
                if titles[season_number]:
                    break
        return titles

    def get_tv_season_years(
        self,
        tmdb_id: int,
        season_numbers: Sequence[int],
        languages: Sequence[str],
    ) -> dict[int, int]:
        years: dict[int, int] = {}
        for season_number in sorted(set(season_numbers)):
            for language in languages:
                payload = self._get(
                    f"/tv/{tmdb_id}/season/{season_number}",
                    {"language": language},
                    swallow_404=True,
                )
                year = year_from_date(payload.get("air_date")) if payload else None
                if year:
                    years[season_number] = year
                    break
        return years

    def get_tv_episode_catalog(
        self,
        tmdb_id: int,
        languages: Sequence[str],
    ) -> TVEpisodeCatalog:
        detail = self._get("/tv/{tmdb_id}".format(tmdb_id=tmdb_id), {"language": languages[0] if languages else "zh-CN"})
        try:
            number_of_seasons = int(detail.get("number_of_seasons") or 0)
        except (TypeError, ValueError):
            number_of_seasons = 0
        seasons: dict[int, dict[int, str]] = {}
        for season_number in [0, *range(1, number_of_seasons + 1)]:
            titles = self.get_tv_episode_titles(tmdb_id, [season_number], languages)
            season_titles = titles.get(season_number, {})
            if season_titles:
                seasons[season_number] = season_titles
        return TVEpisodeCatalog(seasons)

    def _get(self, path: str, params: dict[str, Any] | None = None, *, swallow_404: bool = False) -> dict[str, Any]:
        params = dict(params or {})
        headers = {"Accept": "application/json"}
        if looks_like_bearer_token(self.api_key):
            headers["Authorization"] = f"Bearer {self.api_key.removeprefix('Bearer ').strip()}"
        else:
            params["api_key"] = self.api_key
        query = urlencode({key: value for key, value in params.items() if value is not None})
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        request = Request(url, headers=headers)
        try:
            body = self.requester.read(request, timeout_seconds=self.timeout_seconds)
            return json.loads(body.decode("utf-8"))
        except HTTPError as exc:
            if swallow_404 and exc.code == 404:
                return {}
            raise MatchError(f"TMDB request failed with HTTP {exc.code}: {path}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise MatchError(f"TMDB request failed: {path}: {exc}") from exc
