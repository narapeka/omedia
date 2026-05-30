from __future__ import annotations

import io
import unittest
from email.message import Message
from urllib.error import HTTPError

from app.core.error import ConfigurationError
from app.domain.cache import TMDBDetailCache
from app.domain.media import MediaType
from app.domain.match import TMDBCandidate, TMDBSearchPage, TMDBSearchResult
from app.domain.tv import TVEpisodeCatalog
from app.infra.tmdb.client import TMDBHttpClient
from app.infra.tmdb.metadata import TMDBMetadataService
from app.infra.tmdb.ttl import TTLCache
from app.boot.match import MatchRuntime
from app.services.config.values import ProviderSettings
from support import FakeRequester, make_startup_settings


class FakeTMDBProvider:
    def __init__(self):
        self.detail_calls = 0
        self.lazy_detail_calls = 0
        self.search_calls = 0
        self.episode_title_calls = 0
        self.episode_catalog_calls = 0
        self.season_year_calls = 0

    def get_by_id(self, media_type, tmdb_id):
        self.detail_calls += 1
        return TMDBCandidate(tmdb_id, media_type, f"Detail {self.detail_calls}", year=2020)

    def search_page(self, media_type, title, year, language, page):
        self.search_calls += 1
        return TMDBSearchPage(
            (TMDBSearchResult(self.search_calls, media_type, f"{title} {self.search_calls}", year=year),),
            page=page,
            total_pages=1,
            total_results=1,
        )

    def load_candidate_details(self, media_type, tmdb_id, language, fallback_search_result):
        self.lazy_detail_calls += 1
        return TMDBCandidate(tmdb_id, media_type, f"{fallback_search_result.title} Detail {language}", year=fallback_search_result.year)

    def get_tv_episode_titles(self, tmdb_id, season_numbers, languages):
        self.episode_title_calls += 1
        return {
            int(season): {1: f"Episode {self.episode_title_calls}"}
            for season in season_numbers
        }

    def get_tv_episode_catalog(self, tmdb_id, languages):
        self.episode_catalog_calls += 1
        return TVEpisodeCatalog(
            {
                0: {1: "Special"},
                1: {1: "Pilot"},
                2: {1: "Second Season"},
            }
        )

    def get_tv_season_years(self, tmdb_id, season_numbers, languages):
        self.season_year_calls += 1
        return {int(season): 2020 + self.season_year_calls for season in season_numbers}

class FakeTMDBDetailStore:
    def __init__(self):
        self.details = {}

    def save_tmdb_detail(self, entry: TMDBDetailCache) -> None:
        self.details[(entry.media_type, entry.tmdb_id)] = entry

    def get_tmdb_detail(self, media_type: str, tmdb_id: int) -> TMDBDetailCache | None:
        return self.details.get((media_type, int(tmdb_id)))

    def clear_tmdb_details(self) -> int:
        count = len(self.details)
        self.details.clear()
        return count


class FakeTMDBHttpClient(TMDBHttpClient):
    def __init__(self):
        super().__init__("key")
        self.calls = []

    def _get(self, path, params=None, *, swallow_404=False):
        params = dict(params or {})
        self.calls.append((path, params))
        if path == "/tv/42":
            return {"number_of_seasons": 2}
        if path == "/tv/42/season/0":
            return {"episodes": [{"episode_number": 1, "name": "Special"}]}
        if path == "/tv/42/season/1":
            return {"episodes": [{"episode_number": 1, "name": "Pilot CN"}]}
        if path == "/tv/42/season/2" and params.get("language") == "zh-CN":
            return {"episodes": [{"episode_number": 1, "name": ""}]}
        if path == "/tv/42/season/2" and params.get("language") == "en-US":
            return {"episodes": [{"episode_number": 1, "name": "Season Two EN"}]}
        return {}


class TMDBCacheTests(unittest.TestCase):
    def test_detail_results_are_read_through_persistent_cache(self) -> None:
        provider = FakeTMDBProvider()
        store = FakeTMDBDetailStore()
        client = TMDBMetadataService(provider, store=store)

        detail_1 = client.get_by_id(MediaType.TV, 1)
        detail_2 = client.get_by_id(MediaType.TV, 1)

        self.assertEqual(detail_1, detail_2)
        self.assertEqual(provider.detail_calls, 1)
        self.assertIn(("tv", 1), store.details)

    def test_mismatched_detail_cache_body_is_refetched(self) -> None:
        provider = FakeTMDBProvider()
        store = FakeTMDBDetailStore()
        store.save_tmdb_detail(
            TMDBDetailCache(
                media_type="movie",
                tmdb_id=1,
                metadata={"media_type": "movie", "tmdb_id": 999, "title": "Bad"},
            )
        )
        client = TMDBMetadataService(provider, store=store)

        result = client.get_by_id(MediaType.MOVIE, 1)

        self.assertEqual(provider.detail_calls, 1)
        self.assertEqual(result.tmdb_id, 1)
        self.assertEqual(store.details[("movie", 1)].metadata["tmdb_id"], 1)

    def test_detail_cache_uses_structured_tmdb_titles_only(self) -> None:
        class LocalizedProvider(FakeTMDBProvider):
            def get_by_id(self, media_type, tmdb_id):
                self.detail_calls += 1
                return TMDBCandidate(
                    tmdb_id,
                    media_type,
                    "Preferred CN Title",
                    year=2020,
                    alternative_titles=[
                        {"title": "Preferred CN Title", "iso_3166_1": "CN"},
                    ],
                    translations=[
                        {"title": "Translated SG Title", "iso_3166_1": "SG", "iso_639_1": "zh"},
                    ],
                )

        provider = LocalizedProvider()
        store = FakeTMDBDetailStore()
        client = TMDBMetadataService(provider, store=store)

        client.get_by_id(MediaType.TV, 7)
        cached_body = store.details[("tv", 7)].metadata
        cached_result = client.get_by_id(MediaType.TV, 7)

        self.assertEqual(
            set(cached_body),
            {
                "media_type",
                "tmdb_id",
                "title",
                "original_title",
                "year",
                "alternative_titles",
                "translations",
                "metadata",
            },
        )
        self.assertEqual(cached_body["alternative_titles"][0]["iso_3166_1"], "CN")
        self.assertEqual(cached_result.translations[0]["iso_639_1"], "zh")

    def test_search_results_are_cached_with_ttl(self) -> None:
        now = [0.0]
        provider = FakeTMDBProvider()
        client = TMDBMetadataService(
            provider,
            search_cache=TTLCache(ttl_seconds=10, max_entries=20, now=lambda: now[0]),
        )

        search_1 = client.search_page(MediaType.MOVIE, "Avatar", 2009, "zh-CN", 1)
        search_2 = client.search_page(MediaType.MOVIE, "  avatar  ", 2009, "zh-CN", 1)

        self.assertEqual(provider.search_calls, 1)
        self.assertEqual(len(search_2.results), 1)

        now[0] = 11.0
        refreshed = client.search_page(MediaType.MOVIE, "Avatar", 2009, "zh-CN", 1)

        self.assertEqual(provider.search_calls, 2)
        self.assertNotEqual(search_2.results[0].title, refreshed.results[0].title)

    def test_lru_limit_evicts_old_entries(self) -> None:
        provider = FakeTMDBProvider()
        client = TMDBMetadataService(provider, search_cache=TTLCache(ttl_seconds=60, max_entries=1))

        client.search_page(MediaType.TV, "One", 2020, "zh-CN", 1)
        client.search_page(MediaType.TV, "Two", 2020, "zh-CN", 1)
        client.search_page(MediaType.TV, "One", 2020, "zh-CN", 1)

        self.assertEqual(provider.search_calls, 3)

    def test_search_page_cache_key_distinguishes_year_language_and_page(self) -> None:
        provider = FakeTMDBProvider()
        client = TMDBMetadataService(provider, search_cache=TTLCache(ttl_seconds=60, max_entries=20))

        client.search_page(MediaType.TV, "Example", 2020, "zh-CN", 1)
        client.search_page(MediaType.TV, "Example", None, "zh-CN", 1)
        client.search_page(MediaType.TV, "Example", 2020, "en-US", 1)
        client.search_page(MediaType.TV, "Example", 2020, "zh-CN", 2)
        client.search_page(MediaType.TV, "  example  ", 2020, "zh-CN", 1)

        self.assertEqual(provider.search_calls, 4)

    def test_lazy_search_detail_cache_key_distinguishes_media_id_and_language(self) -> None:
        provider = FakeTMDBProvider()
        client = TMDBMetadataService(provider, detail_cache=TTLCache(ttl_seconds=60, max_entries=20))
        movie_result = TMDBSearchResult(1, MediaType.MOVIE, "Example Movie", year=2020)
        tv_result = TMDBSearchResult(1, MediaType.TV, "Example Show", year=2020)

        client.load_candidate_details(MediaType.MOVIE, 1, "zh-CN", movie_result)
        client.load_candidate_details(MediaType.MOVIE, 1, "zh-CN", movie_result)
        client.load_candidate_details(MediaType.MOVIE, 1, "en-US", movie_result)
        client.load_candidate_details(MediaType.TV, 1, "zh-CN", tv_result)

        self.assertEqual(provider.lazy_detail_calls, 3)

    def test_tv_episode_helpers_are_cached_by_individual_season(self) -> None:
        provider = FakeTMDBProvider()
        client = TMDBMetadataService(
            provider,
            episode_title_cache=TTLCache(ttl_seconds=60, max_entries=20),
            season_year_cache=TTLCache(ttl_seconds=60, max_entries=20),
        )

        titles_1 = client.get_tv_episode_titles(1, [1], ["zh-CN"])
        titles_1[1][1] = "Mutated"
        titles_2 = client.get_tv_episode_titles(1, [1, 2], ["zh-CN"])
        years_1 = client.get_tv_season_years(1, [1], ["zh-CN"])
        years_2 = client.get_tv_season_years(1, [1, 2], ["zh-CN"])

        self.assertEqual(provider.episode_title_calls, 2)
        self.assertEqual(titles_2[1][1], "Episode 1")
        self.assertEqual(provider.season_year_calls, 2)
        self.assertEqual(years_1[1], years_2[1])
        self.assertIn(2, years_2)

    def test_tv_episode_catalog_is_cached_and_reuses_title_cache(self) -> None:
        provider = FakeTMDBProvider()
        client = TMDBMetadataService(
            provider,
            episode_title_cache=TTLCache(ttl_seconds=60, max_entries=20),
            episode_catalog_cache=TTLCache(ttl_seconds=60, max_entries=20),
        )

        catalog_1 = client.get_tv_episode_catalog(1, ["zh-CN"])
        catalog_2 = client.get_tv_episode_catalog(1, ["zh-CN"])
        titles = client.get_tv_episode_titles(1, [0, 1, 2], ["zh-CN"])

        self.assertEqual(provider.episode_catalog_calls, 1)
        self.assertEqual(catalog_1, catalog_2)
        self.assertEqual(titles[0][1], "Special")
        self.assertEqual(titles[1][1], "Pilot")
        self.assertEqual(titles[2][1], "Second Season")
        self.assertEqual(provider.episode_title_calls, 0)

    def test_tmdb_http_tv_episode_catalog_fetches_specials_and_regular_seasons(self) -> None:
        client = FakeTMDBHttpClient()

        catalog = client.get_tv_episode_catalog(42, ["zh-CN", "en-US"])

        self.assertEqual(
            catalog,
            TVEpisodeCatalog(
                {
                    0: {1: "Special"},
                    1: {1: "Pilot CN"},
                    2: {1: "Season Two EN"},
                }
            ),
        )
        self.assertEqual(
            [
                (path, params.get("language"))
                for path, params in client.calls
            ],
            [
                ("/tv/42", "zh-CN"),
                ("/tv/42/season/0", "zh-CN"),
                ("/tv/42/season/1", "zh-CN"),
                ("/tv/42/season/2", "zh-CN"),
                ("/tv/42/season/2", "en-US"),
            ],
        )

    def test_runtime_requires_tmdb_before_loading_tv_episode_catalog(self) -> None:
        runtime = MatchRuntime(make_startup_settings())

        self.assertEqual(runtime.tv_episode_catalog(tmdb_id=None), TVEpisodeCatalog.empty())
        with self.assertRaisesRegex(ConfigurationError, "TMDB provider settings"):
            runtime.tv_episode_catalog(tmdb_id=1)
        self.assertIs(runtime.tv_episode_planner.episode_extractor, runtime)

    def test_runtime_wraps_real_tmdb_client_with_cache(self) -> None:
        runtime = MatchRuntime(
            make_startup_settings(
                providers=ProviderSettings(
                    tmdb_api_key="tmdb-key",
                    tmdb_base_url="https://tmdb.example/3",
                    tmdb_rate_limit=2.5,
                    tmdb_proxy="http://127.0.0.1:10809",
                )
            )
        )

        self.assertIsInstance(runtime.tmdb, TMDBMetadataService)
        self.assertEqual(runtime.tmdb.provider.base_url, "https://tmdb.example/3")
        self.assertEqual(runtime.tmdb.provider.requester.rate_limit, 2.5)
        self.assertEqual(runtime.tmdb.provider.requester.proxy, "http://127.0.0.1:10809")

    def test_runtime_requires_yaml_tmdb_key(self) -> None:
        runtime = MatchRuntime(make_startup_settings(providers=ProviderSettings()))

        with self.assertRaisesRegex(ConfigurationError, "TMDB provider settings"):
            _ = runtime.tmdb

    def test_tmdb_http_client_uses_requester_and_base_url(self) -> None:
        requester = FakeRequester(
            [
                b'{"id": 1, "title": "Avatar", "original_title": "Avatar", "release_date": "2009-12-18"}',
            ]
        )
        client = TMDBHttpClient("key", base_url="https://tmdb.example/3", requester=requester)

        result = client.get_by_id(MediaType.MOVIE, 1)

        self.assertEqual(result.title, "Avatar")
        self.assertEqual(requester.calls[0]["url"], "https://tmdb.example/3/movie/1?language=zh-CN&append_to_response=alternative_titles%2Ctranslations%2Cexternal_ids%2Ccredits&api_key=key")
        self.assertEqual(requester.calls[0]["headers"]["Accept"], "application/json")
        self.assertEqual(requester.calls[0]["timeout_seconds"], 15.0)

    def test_tmdb_http_client_preserves_swallow_404(self) -> None:
        requester = FakeRequester([HTTPError("https://tmdb.example/3/tv/42/season/99", 404, "missing", Message(), io.BytesIO(b""))])
        client = TMDBHttpClient("key", base_url="https://tmdb.example/3", requester=requester)

        result = client.get_tv_episode_titles(42, [99], ["zh-CN"])

        self.assertEqual(result, {})

    def test_tmdb_http_client_includes_manual_search_rich_metadata(self) -> None:
        class RichHTTP(TMDBHttpClient):
            def __init__(self):
                super().__init__("key")

            def _get(self, path, params=None, *, swallow_404=False):
                return {
                    "id": 1,
                    "title": "Avatar",
                    "original_title": "Avatar",
                    "release_date": "2009-12-18",
                    "overview": "A marine on Pandora.",
                    "poster_path": "/poster.jpg",
                    "vote_average": 7.6,
                    "popularity": 88.5,
                    "credits": {
                        "crew": [
                            {"name": "James Cameron", "job": "Director"},
                            {"name": "A Producer", "job": "Producer"},
                        ],
                        "cast": [
                            {"name": "Sam Worthington"},
                            {"name": "Zoe Saldana"},
                        ],
                    },
                    "alternative_titles": {"titles": []},
                    "translations": {"translations": []},
                }

        result = RichHTTP().get_by_id(MediaType.MOVIE, 1)

        self.assertEqual(result.metadata["overview"], "A marine on Pandora.")
        self.assertEqual(result.metadata["poster_path"], "/poster.jpg")
        self.assertEqual(result.metadata["poster_url"], "https://image.tmdb.org/t/p/w154/poster.jpg")
        self.assertEqual(result.metadata["vote_average"], 7.6)
        self.assertEqual(result.metadata["popularity"], 88.5)
        self.assertEqual(result.metadata["directors"], ["James Cameron"])
        self.assertEqual(result.metadata["cast"], ["Sam Worthington", "Zoe Saldana"])

    def test_tmdb_http_client_finds_imdb_id_by_media_type(self) -> None:
        class ExternalHTTP(TMDBHttpClient):
            def __init__(self):
                super().__init__("key")
                self.calls = []

            def _get(self, path, params=None, *, swallow_404=False):
                self.calls.append((path, dict(params or {})))
                if path == "/find/tt0111161":
                    return {
                        "movie_results": [{"id": 278}],
                        "tv_results": [{"id": 999}],
                    }
                if path == "/movie/278":
                    return {
                        "id": 278,
                        "title": "The Shawshank Redemption",
                        "release_date": "1994-09-23",
                        "alternative_titles": {"titles": []},
                        "translations": {"translations": []},
                    }
                raise AssertionError(path)

        client = ExternalHTTP()

        result = client.find_by_external_id("tt0111161", MediaType.MOVIE)

        self.assertEqual(result.tmdb_id, 278)
        self.assertEqual(result.media_type, MediaType.MOVIE)
        self.assertEqual(client.calls[0][0], "/find/tt0111161")
        self.assertEqual(client.calls[0][1]["external_source"], "imdb_id")
        self.assertEqual(client.calls[1][0], "/movie/278")

    def test_tmdb_metadata_service_caches_external_id_lookup(self) -> None:
        provider = FakeTMDBProvider()
        provider.find_by_external_id = lambda imdb_id, media_type: TMDBCandidate(278, media_type, "Cached External", year=1994)
        client = TMDBMetadataService(provider, search_cache=TTLCache(ttl_seconds=60, max_entries=20))

        first = client.find_by_external_id("tt0111161", MediaType.MOVIE)
        second = client.find_by_external_id("TT0111161", MediaType.MOVIE)

        self.assertEqual(first.tmdb_id, 278)
        self.assertEqual(second.tmdb_id, 278)
        self.assertEqual(client.cache_stats().entries, 1)

    def test_tmdb_cache_hit_bypasses_requester(self) -> None:
        store = FakeTMDBDetailStore()
        store.save_tmdb_detail(
            TMDBDetailCache(
                media_type=MediaType.MOVIE.value,
                tmdb_id=1,
                metadata={
                    "media_type": MediaType.MOVIE.value,
                    "tmdb_id": 1,
                    "title": "Cached",
                    "original_title": "Cached",
                    "metadata": {"title": "Cached"},
                },
            )
        )
        requester = FakeRequester([])
        client = TMDBHttpClient("key", requester=requester)
        service = TMDBMetadataService(client, store=store)

        result = service.get_by_id(MediaType.MOVIE, 1)

        self.assertEqual(result.title, "Cached")
        self.assertEqual(requester.calls, [])


if __name__ == "__main__":
    unittest.main()
