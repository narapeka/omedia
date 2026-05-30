from __future__ import annotations

import unittest

from app.domain.match import ConfidenceLevel
from app.domain.media import MediaType
from app.domain.match import TMDBCandidate, TMDBSearchPage, TMDBSearchResult
from app.engines.match.manual import ManualQueryKind, parse_manual_query, rank_title_result
from app.infra.tmdb.metadata import TMDBMetadataService
from app.infra.tmdb.ttl import TTLCache
from app.services.identify.search import ManualTMDBSearchService


class ManualTMDBSearchTests(unittest.TestCase):
    def test_manual_query_parser_accepts_tmdb_and_imdb_forms(self) -> None:
        raw_id = parse_manual_query("12345")
        tmdb_url = parse_manual_query("https://www.themoviedb.org/tv/67890-example")
        imdb_url = parse_manual_query("https://www.imdb.com/title/tt0111161/")
        title = parse_manual_query("The Matrix")

        self.assertEqual(raw_id.kind, ManualQueryKind.TMDB_ID)
        self.assertEqual(raw_id.tmdb_id, 12345)
        self.assertEqual(tmdb_url.kind, ManualQueryKind.TMDB_ID)
        self.assertEqual(tmdb_url.tmdb_id, 67890)
        self.assertEqual(tmdb_url.media_type_hint, MediaType.TV)
        self.assertEqual(imdb_url.kind, ManualQueryKind.IMDB_ID)
        self.assertEqual(imdb_url.imdb_id, "tt0111161")
        self.assertEqual(title.kind, ManualQueryKind.TITLE)
        self.assertEqual(title.title, "The Matrix")

    def test_title_ranking_prefers_exact_title_year_over_title_only_and_popularity(self) -> None:
        exact = TMDBCandidate(
            1,
            MediaType.MOVIE,
            "Avatar",
            year=2009,
            metadata={"popularity": 1},
        )
        popular_wrong_year = TMDBCandidate(
            2,
            MediaType.MOVIE,
            "Avatar",
            year=2010,
            metadata={"popularity": 9999},
        )

        exact_rank = rank_title_result(exact, requested_title="Avatar", requested_year=2009)
        popular_rank = rank_title_result(popular_wrong_year, requested_title="Avatar", requested_year=2009)

        self.assertGreater(exact_rank.score, popular_rank.score)
        self.assertEqual(exact_rank.reason, "exact_title_year_match")
        self.assertEqual(popular_rank.reason, "title_match_year_weakness")
        self.assertEqual(exact_rank.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(popular_rank.confidence, ConfidenceLevel.MEDIUM)

    def test_manual_search_exact_imdb_uses_only_entered_id(self) -> None:
        provider = _ManualSearchProvider()
        provider.external[("tt0111161", MediaType.MOVIE)] = TMDBCandidate(
            99,
            MediaType.MOVIE,
            "The Shawshank Redemption",
            year=1994,
        )

        page = ManualTMDBSearchService(provider).search(
            media_type=MediaType.MOVIE,
            query="tt0111161",
            year=1994,
            fallback_title="Wrong Title",
        )

        self.assertEqual([result.tmdb_id for result in page.results], [99])
        self.assertEqual(page.results[0].reason, "exact_id_match")
        self.assertEqual(provider.search_calls, [])

    def test_manual_search_does_not_use_fallback_year_for_explicit_title(self) -> None:
        provider = _ManualSearchProvider()
        provider.search_pages[("Transformers", None, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1858, MediaType.MOVIE, "Transformers", year=2007),),
            page=1,
            total_pages=1,
            total_results=1,
        )

        page = ManualTMDBSearchService(provider).search(
            media_type=MediaType.MOVIE,
            query="Transformers",
            fallback_title="Silent Fleet",
            fallback_year=2025,
        )

        self.assertEqual([result.tmdb_id for result in page.results], [1858])
        self.assertEqual(provider.search_calls, [("Transformers", None, "zh-CN", 1)])

    def test_manual_search_uses_fallback_context_when_query_missing(self) -> None:
        provider = _ManualSearchProvider()
        provider.search_pages[("Silent Fleet", 2025, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1450115, MediaType.MOVIE, "Silent Fleet", year=2025),),
            page=1,
            total_pages=1,
            total_results=1,
        )

        page = ManualTMDBSearchService(provider).search(
            media_type=MediaType.MOVIE,
            fallback_title="Silent Fleet",
            fallback_year=2025,
        )

        self.assertEqual([result.tmdb_id for result in page.results], [1450115])
        self.assertEqual(provider.search_calls, [("Silent Fleet", 2025, "zh-CN", 1)])

    def test_manual_search_filters_tmdb_url_media_type(self) -> None:
        provider = _ManualSearchProvider()
        provider.details[(MediaType.MOVIE, 10)] = TMDBCandidate(10, MediaType.MOVIE, "Movie")

        page = ManualTMDBSearchService(provider).search(
            media_type=MediaType.TV,
            query="https://www.themoviedb.org/movie/10",
        )

        self.assertEqual(page.results, ())
        self.assertEqual(provider.detail_calls, [])

    def test_manual_search_returns_rich_metadata(self) -> None:
        provider = _ManualSearchProvider()
        provider.search_pages[("Avatar", 2009, "zh-CN", 1)] = TMDBSearchPage(
            (
                TMDBCandidate(
                    19995,
                    MediaType.MOVIE,
                    "Avatar",
                    original_title="Avatar",
                    year=2009,
                    metadata={
                        "overview": "A marine on Pandora.",
                        "poster_url": "https://image.tmdb.org/t/p/w154/poster.jpg",
                        "vote_average": 7.6,
                        "popularity": 88.5,
                    },
                ),
            ),
            page=1,
            total_pages=2,
            total_results=20,
        )

        page = ManualTMDBSearchService(provider).search(
            media_type=MediaType.MOVIE,
            query="Avatar",
            year=2009,
        )

        result = page.results[0]
        self.assertEqual(result.tmdb_id, 19995)
        self.assertEqual(result.overview, "A marine on Pandora.")
        self.assertEqual(result.poster_url, "https://image.tmdb.org/t/p/w154/poster.jpg")
        self.assertEqual(result.vote_average, 7.6)
        self.assertEqual(result.popularity, 88.5)
        self.assertEqual(page.page, 1)
        self.assertEqual(page.total_pages, 2)
        self.assertEqual(page.total_results, 20)

    def test_manual_search_uses_existing_search_cache_boundary(self) -> None:
        provider = _ManualSearchProvider()
        provider.search_pages[("Avatar", 2009, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(19995, MediaType.MOVIE, "Avatar", year=2009),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        cached_tmdb = TMDBMetadataService(
            provider,
            search_cache=TTLCache(ttl_seconds=60, max_entries=20),
        )
        service = ManualTMDBSearchService(cached_tmdb)

        service.search(media_type=MediaType.MOVIE, query="Avatar", year=2009)
        service.search(media_type=MediaType.MOVIE, query="  Avatar  ", year=2009)

        self.assertEqual(provider.search_calls, [("Avatar", 2009, "zh-CN", 1)])


class _ManualSearchProvider:
    def __init__(self):
        self.details = {}
        self.external = {}
        self.search_pages = {}
        self.detail_calls = []
        self.lazy_detail_calls = []
        self.search_calls = []
        self.external_calls = []

    def get_by_id(self, media_type, tmdb_id):
        self.detail_calls.append((media_type, int(tmdb_id)))
        return self.details.get((media_type, int(tmdb_id)))

    def find_by_external_id(self, imdb_id, media_type):
        self.external_calls.append((imdb_id, media_type))
        return self.external.get((imdb_id, media_type))

    def search_page(self, media_type, title, year, language, page):
        self.search_calls.append((title, year, language, page))
        value = self.search_pages.get(
            (title, year, language, page),
            TMDBSearchPage(page=page),
        )
        if isinstance(value, TMDBSearchPage):
            return TMDBSearchPage(
                tuple(self._search_result(item, language) for item in value.results),
                page=value.page,
                total_pages=value.total_pages,
                total_results=value.total_results,
            )
        return value

    def load_candidate_details(self, media_type, tmdb_id, language, fallback_search_result):
        self.lazy_detail_calls.append((media_type, int(tmdb_id), language))
        return (
            self.details.get((media_type, int(tmdb_id), language))
            or self.details.get((media_type, int(tmdb_id)))
            or fallback_search_result.to_candidate()
        )

    def _search_result(self, item, language):
        if isinstance(item, TMDBSearchResult):
            return item
        if isinstance(item, TMDBCandidate):
            self.details.setdefault((item.media_type, item.tmdb_id, language), item)
            return TMDBSearchResult(
                item.tmdb_id,
                item.media_type,
                item.title,
                original_title=item.original_title,
                year=item.year,
                metadata=dict(item.metadata),
            )
        return item

    def get_tv_episode_titles(self, tmdb_id, season_numbers, languages):
        return {}

    def get_tv_season_years(self, tmdb_id, season_numbers, languages):
        return {}

    def get_tv_episode_catalog(self, tmdb_id, languages):
        return None


if __name__ == "__main__":
    unittest.main()
