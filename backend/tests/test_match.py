from __future__ import annotations

import unittest
from pathlib import Path

from app.domain.match import ConfidenceLevel, YearMatch
from app.domain.media import MediaType
from app.domain.media import MediaCandidate, MediaFile
from app.core.error import MatchError
from app.services.identify.match import MatchService
from app.domain.match import HintSource, MatchHint, TMDBCandidate, TMDBSearchPage, TMDBSearchResult, TitleHint, TitleKind
from app.infra.llm.prompt import PromptSet
from app.infra.llm.episode import validate_results
from app.infra.llm.payload import hint_from_payload, loads_json_from_content
from app.engines.match.hint import HintExtractor
from app.engines.match.confidence import classify_year_match
from app.infra.tmdb.client import TMDBHttpClient
from app.infra.tmdb.title import OPENCC_CONVERTER
from support import BatchLLMHintExtractor, FakeTMDB, FixedLLMHintExtractor, FixedMediaNameExtractor, TEST_MEDIA_EXTENSIONS


def _hint(
    title: str | None = None,
    *,
    year: int | None = None,
    tmdb_id: int | None = None,
    kind: TitleKind = TitleKind.SOURCE,
    source: HintSource = HintSource.DETERMINISTIC,
    titles: tuple[TitleHint, ...] | None = None,
) -> MatchHint:
    if titles is None:
        titles = (TitleHint(title, kind, source),) if title else ()
    return MatchHint(titles=titles, year=year, tmdb_id=tmdb_id)


def _empty_llm() -> FixedLLMHintExtractor:
    return FixedLLMHintExtractor(MatchHint())


class MatchTests(unittest.TestCase):
    def test_direct_tmdb_id_lookup_for_tv_and_movie(self) -> None:
        tmdb = FakeTMDB()
        tmdb.by_id[(MediaType.TV, 1)] = TMDBCandidate(1, MediaType.TV, "Example Show", year=2020)
        tmdb.by_id[(MediaType.MOVIE, 2)] = TMDBCandidate(2, MediaType.MOVIE, "Example Movie", year=2021)

        tv_result = MatchService(tmdb, media_name_extractor=FixedMediaNameExtractor(_hint(tmdb_id=1)), llm_extractor=_empty_llm()).match(
            self._candidate(MediaType.TV, "Whatever")
        )
        movie_result = MatchService(tmdb, media_name_extractor=FixedMediaNameExtractor(_hint(tmdb_id=2)), llm_extractor=_empty_llm()).match(
            self._candidate(MediaType.MOVIE, "Whatever")
        )

        self.assertEqual(tv_result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(movie_result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(tv_result.tmdb_id, 1)
        self.assertEqual(movie_result.tmdb_id, 2)
        self.assertEqual(tmdb.search_calls, [])

    def test_multilingual_title_matching_and_confidence(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_results = [
            TMDBCandidate(
                1,
                MediaType.TV,
                "English Title",
                year=2020,
                translations=[{"title": "Example Show", "iso_3166_1": "US", "iso_639_1": "en"}],
            )
        ]
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("Example Show", year=2020)),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", year=2020, kind=TitleKind.CHINESE, source=HintSource.LLM)
            ),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.2020"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(tmdb.search_calls[0]["language"], "zh-CN")

    def test_single_result_without_source_title_match_is_medium_confidence(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_results = [TMDBCandidate(1, MediaType.TV, "Different Show", year=2020)]
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("Different Show", year=2020)),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Different Show", year=2020, kind=TitleKind.ENGLISH, source=HintSource.LLM)
            ),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show"))

        self.assertEqual(result.confidence, ConfidenceLevel.MEDIUM)

    def test_llm_hint_is_used_as_extraction_source_before_tmdb_search(self) -> None:
        class TitleAwareTMDB(FakeTMDB):
            def search_page(self, media_type, title, year, language, page):
                self.search_calls.append(
                    {"media_type": media_type, "title": title, "year": year, "language": language, "page": page}
                )
                self.last_title = title
                if title == "Example Show":
                    return self._search_page_from_results(
                        (TMDBCandidate(1, media_type, "Example Show", year=2020),),
                        page=page,
                        total_pages=1,
                        total_results=1,
                        language=language,
                    )
                return TMDBSearchPage(page=page)

        matcher = MatchService(
            TitleAwareTMDB(),
            media_name_extractor=FixedMediaNameExtractor(_hint("No Match")),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", year=2020, kind=TitleKind.ENGLISH, source=HintSource.LLM)
            ),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.2020"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.tmdb_id, 1)
        self.assertIn("llm_hint", [item.source for item in result.evidence])

    def test_source_tmdb_id_is_preserved_when_llm_supplies_title(self) -> None:
        tmdb = FakeTMDB()
        tmdb.by_id[(MediaType.TV, 42)] = TMDBCandidate(42, MediaType.TV, "Example Show", year=2020)
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("Example", tmdb_id=42)),
            llm_extractor=FixedLLMHintExtractor(_hint("LLM Title", kind=TitleKind.ENGLISH, source=HintSource.LLM)),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.{tmdb-42}"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.tmdb_id, 42)

    def test_match_batch_uses_batch_llm_hints(self) -> None:
        class TitleAwareTMDB(FakeTMDB):
            def search_page(self, media_type, title, year, language, page):
                self.search_calls.append(
                    {"media_type": media_type, "title": title, "year": year, "language": language, "page": page}
                )
                if title == "Batch Title":
                    return self._search_page_from_results(
                        (TMDBCandidate(7, media_type, "Batch Title", year=2020),),
                        page=page,
                        total_pages=1,
                        total_results=1,
                        language=language,
                    )
                return TMDBSearchPage(page=page)

        candidate = self._candidate(MediaType.TV, "Batch.Title.2020")
        llm = BatchLLMHintExtractor(
            {candidate.id: _hint("Batch Title", year=2020, kind=TitleKind.ENGLISH, source=HintSource.LLM)}
        )
        matcher = MatchService(
            TitleAwareTMDB(),
            media_name_extractor=FixedMediaNameExtractor(_hint("Bad Title")),
            llm_extractor=llm,
        )

        results = matcher.match_batch([candidate], llm_batch_size=12)

        self.assertEqual(results[candidate.id].confidence, ConfidenceLevel.HIGH)
        self.assertEqual(results[candidate.id].tmdb_id, 7)
        self.assertEqual(llm.batch_calls, [((candidate.id,), 12)])
        self.assertEqual(llm.single_calls, 0)

    def test_llm_media_match_payload_preserves_structured_title_hints(self) -> None:
        hint = hint_from_payload(
            {
                "chinese_title": "Chinese Title",
                "english_title": "English Title",
                "year": "2020",
                "tmdb_id": "123",
            }
        )

        self.assertEqual(hint.year, 2020)
        self.assertEqual(hint.tmdb_id, 123)
        self.assertEqual(
            [(title.kind, title.value, title.source) for title in hint.titles],
            [
                (TitleKind.CHINESE, "Chinese Title", HintSource.LLM),
                (TitleKind.ENGLISH, "English Title", HintSource.LLM),
            ],
        )

    def test_llm_media_match_payload_ignores_unsupported_titles_and_short_years(self) -> None:
        hint = hint_from_payload(
            {
                "title": "Noisy Primary",
                "original_title": "Original Title",
                "aliases": ["Alias One"],
                "cn_name": "Legacy Chinese",
                "en_name": "Legacy English",
                "year": "24",
            }
        )

        self.assertEqual(hint.titles, ())
        self.assertIsNone(hint.year)

    def test_search_strategy_order_is_explicit_and_local_to_match_chain(self) -> None:
        tmdb = FakeTMDB()
        matcher = MatchService(tmdb, media_name_extractor=FixedMediaNameExtractor(_hint(
            year=2020,
            titles=(
                TitleHint("Primary Title", TitleKind.SOURCE, HintSource.DETERMINISTIC),
                TitleHint("Chinese Title", TitleKind.CHINESE, HintSource.LLM),
                TitleHint("English Title", TitleKind.ENGLISH, HintSource.LLM),
            ),
        )), llm_extractor=_empty_llm(), languages=("zh-CN",))

        matcher.match(self._candidate(MediaType.TV, "No.Match.2020"))

        self.assertEqual(
            [(call["title"], call["year"]) for call in tmdb.search_calls],
            [
                ("Chinese Title", None),
                ("English Title", None),
                ("Chinese Title", 2020),
                ("English Title", 2020),
            ],
        )
    def test_source_title_does_not_create_automatic_search_when_llm_titles_are_absent(self) -> None:
        tmdb = FakeTMDB()
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("Source Title", year=2020)),
            llm_extractor=_empty_llm(),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Source.Title.2020"))

        self.assertEqual(tmdb.search_calls, [])
        self.assertEqual(result.confidence, ConfidenceLevel.NONE)
        self.assertTrue(result.evidence[-1].values["no_title_search_skipped"])

    def test_year_match_classification_shared_vocabulary(self) -> None:
        self.assertEqual(classify_year_match(2020, 2020), YearMatch.EXACT)
        self.assertEqual(classify_year_match(2020, 2021), YearMatch.FUZZY)
        self.assertEqual(classify_year_match(None, 2021), YearMatch.MISSING)
        self.assertEqual(classify_year_match(2020, 2022), YearMatch.MISMATCH)

    def test_movie_missing_tmdb_year_is_medium_not_high(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Day Dreaming", None, "en-US", 1)] = TMDBSearchPage(
            (TMDBCandidate(1374948, MediaType.MOVIE, "Day Dreaming", year=None),),
            page=1,
            total_pages=1,
            total_results=7,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("Day Dreaming", year=2025)),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Day Dreaming", year=2025, kind=TitleKind.ENGLISH, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.MOVIE, "Day.Dreaming.2025.2160p.WEB-DL"))

        self.assertEqual(result.confidence, ConfidenceLevel.MEDIUM)
        self.assertEqual(result.tmdb_id, 1374948)
        self.assertEqual(result.evidence[-1].values["attempted_strategies"][-1]["year_match"], "missing")
        self.assertEqual(
            result.evidence[-1].values["attempted_strategies"][-1]["confidence_rule"],
            "non_source_exact_known_title",
        )

    def test_tv_missing_tmdb_year_is_medium_not_high(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Show", None, "en-US", 1)] = TMDBSearchPage(
            (TMDBCandidate(12, MediaType.TV, "Example Show", year=None),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("Example Show", year=2025)),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", year=2025, kind=TitleKind.ENGLISH, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.2025"))

        self.assertEqual(result.confidence, ConfidenceLevel.MEDIUM)
        self.assertEqual(result.tmdb_id, 12)
        self.assertEqual(result.evidence[-1].values["attempted_strategies"][0]["year_match"], "missing")
        self.assertEqual(
            result.evidence[-1].values["attempted_strategies"][0]["confidence_rule"],
            "non_source_exact_known_title",
        )

    def test_one_year_fuzzy_title_match_remains_high(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Movie", 2025, "en-US", 1)] = TMDBSearchPage(
            (TMDBCandidate(13, MediaType.MOVIE, "Example Movie", year=2024),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("Example Movie", year=2025)),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Movie", year=2025, kind=TitleKind.ENGLISH, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.MOVIE, "Example.Movie.2025"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.evidence[-1].values["attempted_strategies"][0]["year_match"], "fuzzy")

    def test_later_language_high_beats_earlier_missing_year_medium(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Day Dreaming", None, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1374948, MediaType.MOVIE, "Day Dreaming", year=None),),
            page=1,
            total_pages=1,
            total_results=7,
        )
        tmdb.search_pages[("Day Dreaming", None, "en-US", 1)] = TMDBSearchPage(
            (
                TMDBCandidate(
                    1136557,
                    MediaType.MOVIE,
                    "漫漫长日",
                    original_title="朱同在三年级丢失了超能力",
                    year=2024,
                    alternative_titles=[{"title": "Day Dreaming", "iso_3166_1": "CN"}],
                ),
                TMDBCandidate(1374948, MediaType.MOVIE, "Day Dreaming", year=None),
            ),
            page=1,
            total_pages=1,
            total_results=7,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("Day Dreaming", year=2025)),
            llm_extractor=FixedLLMHintExtractor(
                _hint(
                    year=2025,
                    titles=(
                        TitleHint("Day Dreaming", TitleKind.CHINESE, HintSource.LLM),
                        TitleHint("Day Dreaming", TitleKind.ENGLISH, HintSource.LLM),
                    ),
                )
            ),
            languages=("zh-CN", "en-US"),
        )

        result = matcher.match(self._candidate(MediaType.MOVIE, "Day.Dreaming.2025.2160p.WEB-DL"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.tmdb_id, 1136557)
        attempts = result.evidence[-1].values["attempted_strategies"]
        self.assertEqual(attempts[-2]["selected_tmdb_id"], 1374948)
        self.assertEqual(attempts[-2]["confidence"], "medium")
        self.assertEqual(attempts[-1]["selected_tmdb_id"], 1136557)
        self.assertEqual(attempts[-1]["year_match"], "fuzzy")

    def test_non_source_exact_known_title_is_medium_when_high_fails(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Movie", 2020, "en-US", 1)] = TMDBSearchPage(
            (TMDBCandidate(10, MediaType.MOVIE, "Example Movie", year=2020),),
            page=1,
            total_pages=1,
            total_results=5,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("Noisy Source", year=2020)),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Movie", year=2020, kind=TitleKind.ENGLISH, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.MOVIE, "Noisy.Source.2020"))

        self.assertEqual(result.confidence, ConfidenceLevel.MEDIUM)
        self.assertEqual(result.tmdb_id, 10)
        self.assertEqual(result.evidence[-1].values["selected_strategy"]["title_kind"], "english")
        self.assertEqual(result.evidence[-1].values["attempted_strategies"][0]["confidence_rule"], "non_source_exact_known_title")

    def test_exact_known_title_missing_year_low_ambiguity_is_medium_when_high_fails(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Movie", None, "en-US", 1)] = TMDBSearchPage(
            (TMDBCandidate(11, MediaType.MOVIE, "Example Movie", year=2020),),
            page=1,
            total_pages=1,
            total_results=3,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("Example Movie")),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Movie", kind=TitleKind.ENGLISH, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.MOVIE, "Noisy.Source"))

        self.assertEqual(result.confidence, ConfidenceLevel.MEDIUM)
        self.assertEqual(result.tmdb_id, 11)
        self.assertEqual(result.evidence[-1].values["attempted_strategies"][0]["confidence_rule"], "non_source_exact_known_title")

    def test_no_candidate_result_is_none_confidence(self) -> None:
        matcher = MatchService(
            FakeTMDB(),
            media_name_extractor=FixedMediaNameExtractor(MatchHint()),
            llm_extractor=_empty_llm(),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.MOVIE, "No.Identity"))

        self.assertEqual(result.confidence, ConfidenceLevel.NONE)
        self.assertIsNone(result.tmdb_id)

    def test_english_fallback_succeeds_after_chinese_search_is_not_high(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Chinese Title", 2020, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1, MediaType.TV, "Different Show", year=2020),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        tmdb.search_pages[("Example Show", 2020, "en-US", 1)] = TMDBSearchPage(
            (TMDBCandidate(2, MediaType.TV, "Example Show", year=2020),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        matcher = MatchService(tmdb, media_name_extractor=FixedMediaNameExtractor(_hint(
            year=2020,
            titles=(
                TitleHint("Chinese Title", TitleKind.CHINESE, HintSource.LLM),
                TitleHint("Example Show", TitleKind.ENGLISH, HintSource.LLM),
            ),
        )), llm_extractor=_empty_llm(), languages=("zh-CN",))

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.2020"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.tmdb_id, 2)

    def test_no_year_strategy_still_validates_extracted_year(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Show", None, "en-US", 1)] = TMDBSearchPage(
            (TMDBCandidate(9, MediaType.TV, "Example Show", year=2015),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("Example Show", year=2020)),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", year=2020, kind=TitleKind.ENGLISH, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.2020"))

        self.assertEqual(result.confidence, ConfidenceLevel.LOW)
        self.assertEqual(result.tmdb_id, 9)

    def test_tv_later_season_suppresses_show_year_search_and_validates_season_year(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Show", None, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1, MediaType.TV, "Example Show", year=2020),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        tmdb.season_years[(1, 2)] = 2022
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", kind=TitleKind.CHINESE, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.S02.2022", files=("E01.mkv",), structure="direct_files"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.tmdb_id, 1)
        self.assertEqual([(call["title"], call["year"]) for call in tmdb.search_calls], [("Example Show", None)])
        self.assertEqual(tmdb.season_year_calls[0]["seasons"], (2,))
        search_evidence = result.evidence[-1].values
        validation = search_evidence["selected_tv_year_validation"]
        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["facts"][0]["matched_by"], "season_year")
        self.assertTrue(search_evidence["selected_strategy"]["search_year_suppressed"])

    def test_tv_later_season_downgrade_continues_to_next_candidate(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Show", None, "zh-CN", 1)] = TMDBSearchPage(
            (
                TMDBCandidate(1, MediaType.TV, "Example Show", year=2020),
                TMDBCandidate(2, MediaType.TV, "Example Show", year=2018),
            ),
            page=1,
            total_pages=1,
            total_results=2,
        )
        tmdb.season_years[(1, 2)] = 2024
        tmdb.season_years[(2, 2)] = 2022
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", kind=TitleKind.CHINESE, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.S02.2022", files=("E01.mkv",), structure="direct_files"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.tmdb_id, 2)
        self.assertEqual([call["tmdb_id"] for call in tmdb.season_year_calls], [1, 2])

    def test_tv_later_season_missing_season_year_downgrades(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Show", None, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1, MediaType.TV, "Example Show", year=2020),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", kind=TitleKind.CHINESE, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.S02.2022", files=("E01.mkv",), structure="direct_files"))

        self.assertEqual(result.confidence, ConfidenceLevel.LOW)
        validation = result.evidence[-1].values["selected_tv_year_validation"]
        self.assertEqual(validation["status"], "failed")
        self.assertEqual(validation["facts"][0]["status"], "unavailable")

    def test_failed_tv_year_validation_downgrades_medium_to_low(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Wrong Show", None, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1, MediaType.TV, "Different Show", year=2020),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Wrong Show", kind=TitleKind.CHINESE, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Wrong.Show.S02.2022", files=("E01.mkv",), structure="direct_files"))

        self.assertEqual(result.confidence, ConfidenceLevel.LOW)
        validation = result.evidence[-1].values["selected_tv_year_validation"]
        self.assertEqual(validation["status"], "failed")
        self.assertEqual(validation["downgraded_from"], "medium")
        self.assertEqual(validation["downgraded_to"], "low")

    def test_tv_child_season_year_validates_without_show_year_search(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Show", None, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1, MediaType.TV, "Example Show", year=2020),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        tmdb.season_years[(1, 2)] = 2022
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", kind=TitleKind.CHINESE, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(
            self._candidate(
                MediaType.TV,
                "Example.Show",
                files=("Season 2 2022/E01.mkv",),
                structure="season_subfolders",
            )
        )

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(tmdb.search_calls[0]["year"], None)
        self.assertEqual(tmdb.season_year_calls[0]["seasons"], (2,))

    def test_mixed_tv_candidate_validates_direct_and_child_year_facts(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Show", None, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1, MediaType.TV, "Example Show", year=2020),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        tmdb.season_years[(1, 2)] = 2022
        tmdb.season_years[(1, 3)] = 2023
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", kind=TitleKind.CHINESE, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(
            self._candidate(
                MediaType.TV,
                "Example.Show.S02.2022",
                files=("E01.mkv", "Season 3 2023/E01.mkv"),
                structure="mixed",
            )
        )

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        validation = result.evidence[-1].values["selected_tv_year_validation"]
        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["season_year_lookup_requested"], [2, 3])
        self.assertEqual([fact["scope"] for fact in validation["facts"]], ["show_or_season_year", "season_year"])

    def test_ordinary_tv_show_year_uses_search_year_and_skips_season_year_lookup(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Show", 2020, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1, MediaType.TV, "Example Show", year=2020),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", kind=TitleKind.CHINESE, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.2020", files=("E01.mkv",), structure="direct_files"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(tmdb.search_calls[0]["year"], 2020)
        self.assertEqual(tmdb.season_year_calls, [])

    def test_explicit_season_one_tv_folder_keeps_ordinary_show_year_behavior(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Show", 2020, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1, MediaType.TV, "Example Show", year=2020),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", kind=TitleKind.CHINESE, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.S01.2020", files=("E01.mkv",), structure="direct_files"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(tmdb.search_calls[0]["year"], 2020)
        self.assertEqual(tmdb.season_year_calls, [])

    def test_movie_match_does_not_request_tv_season_years(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Movie", 2020, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1, MediaType.MOVIE, "Example Movie", year=2020),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Movie", kind=TitleKind.CHINESE, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.MOVIE, "Example.Movie.2020"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(tmdb.season_year_calls, [])

    def test_high_confidence_on_page_one_skips_extra_pages(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Show", 2020, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1, MediaType.TV, "Example Show", year=2020),),
            page=1,
            total_pages=5,
            total_results=50,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", kind=TitleKind.CHINESE, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.2020"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual([call["page"] for call in tmdb.search_calls], [1])

    def test_extra_page_fallback_is_bounded_and_records_evidence(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Show", 2020, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1, MediaType.TV, "Different Show", year=2020),),
            page=1,
            total_pages=5,
            total_results=50,
        )
        tmdb.search_pages[("Example Show", 2020, "zh-CN", 2)] = TMDBSearchPage(
            (),
            page=2,
            total_pages=5,
            total_results=50,
        )
        tmdb.search_pages[("Example Show", 2020, "zh-CN", 3)] = TMDBSearchPage(
            (),
            page=3,
            total_pages=5,
            total_results=50,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", kind=TitleKind.CHINESE, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
            max_search_pages=3,
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.2020"))
        search_evidence = result.evidence[-1].values

        self.assertEqual(result.confidence, ConfidenceLevel.LOW)
        self.assertEqual([call["page"] for call in tmdb.search_calls if call["year"] == 2020], [1, 2, 3])
        self.assertEqual(search_evidence["pagination_reason"], "page_bound_reached")
        self.assertEqual(search_evidence["selected_strategy"]["title"], "Example Show")
        self.assertGreaterEqual(search_evidence["attempted_strategy_count"], 3)

    def test_page_one_candidate_after_position_five_is_evaluated_before_extra_pages(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Show", 2020, "zh-CN", 1)] = TMDBSearchPage(
            tuple(
                TMDBCandidate(index, MediaType.TV, "Different Show", year=2020)
                for index in range(1, 6)
            )
            + (TMDBCandidate(6, MediaType.TV, "Example Show", year=2020),),
            page=1,
            total_pages=2,
            total_results=25,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", kind=TitleKind.CHINESE, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
            max_search_pages=2,
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.2020", files=("E01.mkv",), structure="direct_files"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.tmdb_id, 6)
        self.assertEqual([call["page"] for call in tmdb.search_calls], [1])
        self.assertEqual([call[1] for call in tmdb.detail_calls], [1, 2, 3, 4, 5, 6])

    def test_later_strategy_page_one_runs_before_first_strategy_extra_page(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Chinese Title", 2020, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1, MediaType.MOVIE, "Wrong Movie", year=2020),),
            page=1,
            total_pages=3,
            total_results=40,
        )
        tmdb.search_pages[("English Title", 2020, "en-US", 1)] = TMDBSearchPage(
            (
                TMDBCandidate(2, MediaType.MOVIE, "Wrong Movie", year=2020),
                TMDBCandidate(3, MediaType.MOVIE, "English Title", year=2020),
            ),
            page=1,
            total_pages=1,
            total_results=2,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("English Title", year=2020)),
            llm_extractor=FixedLLMHintExtractor(
                _hint(
                    year=2020,
                    titles=(
                        TitleHint("Chinese Title", TitleKind.CHINESE, HintSource.LLM),
                        TitleHint("English Title", TitleKind.ENGLISH, HintSource.LLM),
                    ),
                )
            ),
            max_search_pages=3,
        )

        result = matcher.match(self._candidate(MediaType.MOVIE, "English.Title.2020"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.tmdb_id, 3)
        self.assertEqual(
            [(call["title"], call["page"]) for call in tmdb.search_calls],
            [("Chinese Title", 1), ("English Title", 1)],
        )

    def test_high_confidence_first_candidate_fetches_only_one_detail(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Show", 2020, "zh-CN", 1)] = TMDBSearchPage(
            (
                TMDBCandidate(1, MediaType.TV, "Example Show", year=2020),
                TMDBCandidate(2, MediaType.TV, "Example Show", year=2020),
            ),
            page=1,
            total_pages=2,
            total_results=30,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", kind=TitleKind.CHINESE, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.2020", files=("E01.mkv",), structure="direct_files"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.tmdb_id, 1)
        self.assertEqual([call[1] for call in tmdb.detail_calls], [1])

    def test_non_high_selection_preserves_first_candidate_in_highest_bucket(self) -> None:
        scenarios = [
            ("medium_low_medium", ("Target", "Other", "Target"), 1),
            ("low_medium_low", ("Other", "Target", "Other Again"), 2),
            ("all_low", ("Other", "Other Again", "Still Other"), 1),
        ]
        for name, titles, expected_tmdb_id in scenarios:
            with self.subTest(name=name):
                tmdb = FakeTMDB()
                tmdb.search_results = [
                    TMDBCandidate(index, MediaType.MOVIE, title)
                    for index, title in enumerate(titles, start=1)
                ]
                matcher = MatchService(
                    tmdb,
                    media_name_extractor=FixedMediaNameExtractor(_hint("Noisy Source")),
                    llm_extractor=FixedLLMHintExtractor(
                        _hint("Target", kind=TitleKind.ENGLISH, source=HintSource.LLM)
                    ),
                )

                result = matcher.match(self._candidate(MediaType.MOVIE, "Noisy.Source"))

                self.assertEqual(result.tmdb_id, expected_tmdb_id)

    def test_lazy_detail_enrichment_preserves_translation_match(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Show", 2020, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBSearchResult(10, MediaType.TV, "Untranslated Title", year=2020),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        tmdb.details[(MediaType.TV, 10, "zh-CN")] = TMDBCandidate(
            10,
            MediaType.TV,
            "Untranslated Title",
            year=2020,
            translations=[{"title": "Example Show", "iso_3166_1": "US", "iso_639_1": "en"}],
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Show", kind=TitleKind.CHINESE, source=HintSource.LLM)
            ),
            languages=("zh-CN",),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.2020", files=("E01.mkv",), structure="direct_files"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.tmdb_id, 10)
        self.assertEqual(tmdb.detail_calls, [(MediaType.TV, 10, "zh-CN")])

    def test_lazy_detail_lookup_uses_strategy_language(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Chinese Title", None, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBSearchResult(20, MediaType.TV, "Search Row", year=2020),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        tmdb.search_pages[("English Title", None, "en-US", 1)] = TMDBSearchPage(
            (TMDBSearchResult(20, MediaType.TV, "Search Row", year=2020),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        tmdb.details[(MediaType.TV, 20, "zh-CN")] = TMDBCandidate(20, MediaType.TV, "Wrong Title", year=2020)
        tmdb.details[(MediaType.TV, 20, "en-US")] = TMDBCandidate(20, MediaType.TV, "English Title", year=2020)
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("English Title")),
            llm_extractor=FixedLLMHintExtractor(
                _hint(
                    year=2020,
                    titles=(
                        TitleHint("Chinese Title", TitleKind.CHINESE, HintSource.LLM),
                        TitleHint("English Title", TitleKind.ENGLISH, HintSource.LLM),
                    )
                )
            ),
        )

        result = matcher.match(self._candidate(MediaType.TV, "English.Title.2020"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.tmdb_id, 20)
        self.assertEqual(tmdb.detail_calls, [(MediaType.TV, 20, "zh-CN"), (MediaType.TV, 20, "en-US")])

    def test_regional_languages_are_not_used_for_automatic_title_search(self) -> None:
        tmdb = FakeTMDB()
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("Noisy Source")),
            llm_extractor=FixedLLMHintExtractor(
                _hint(
                    titles=(
                        TitleHint("Chinese Title", TitleKind.CHINESE, HintSource.LLM),
                        TitleHint("English Title", TitleKind.ENGLISH, HintSource.LLM),
                    )
                )
            ),
            languages=("zh-CN", "zh-SG", "zh-TW", "zh-HK", "en-US"),
        )

        matcher.match(self._candidate(MediaType.MOVIE, "Noisy.Source"))

        self.assertEqual([call["language"] for call in tmdb.search_calls], ["zh-CN", "en-US"])

    def test_movie_with_year_strategy_runs_before_no_year_fallback(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Example Movie", None, "en-US", 1)] = TMDBSearchPage(
            (TMDBCandidate(1, MediaType.MOVIE, "Example Movie", year=2020),),
            page=1,
            total_pages=1,
            total_results=1,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("Example Movie", year=2020)),
            llm_extractor=FixedLLMHintExtractor(
                _hint("Example Movie", year=2020, kind=TitleKind.ENGLISH, source=HintSource.LLM)
            ),
        )

        result = matcher.match(self._candidate(MediaType.MOVIE, "Example.Movie.2020"))

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(
            [(call["year"], call["language"]) for call in tmdb.search_calls],
            [(2020, "en-US"), (None, "en-US")],
        )

    def test_extra_page_fallback_uses_first_page_eligible_strategy_not_strongest_non_high(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_pages[("Chinese Title", 2020, "zh-CN", 1)] = TMDBSearchPage(
            (TMDBCandidate(1, MediaType.MOVIE, "Wrong Movie", year=2020),),
            page=1,
            total_pages=3,
            total_results=40,
        )
        tmdb.search_pages[("English Title", 2020, "en-US", 1)] = TMDBSearchPage(
            (TMDBCandidate(2, MediaType.MOVIE, "English Title", year=2020),),
            page=1,
            total_pages=3,
            total_results=40,
        )
        tmdb.search_pages[("Chinese Title", 2020, "zh-CN", 2)] = TMDBSearchPage(
            (),
            page=2,
            total_pages=3,
            total_results=40,
        )
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("Noisy Source", year=2020)),
            llm_extractor=FixedLLMHintExtractor(
                _hint(
                    year=2020,
                    titles=(
                        TitleHint("Chinese Title", TitleKind.CHINESE, HintSource.LLM),
                        TitleHint("English Title", TitleKind.ENGLISH, HintSource.LLM),
                    ),
                )
            ),
            max_search_pages=2,
        )

        result = matcher.match(self._candidate(MediaType.MOVIE, "Noisy.Source.2020"))

        self.assertEqual(result.confidence, ConfidenceLevel.MEDIUM)
        self.assertEqual(result.tmdb_id, 2)
        self.assertIn(("Chinese Title", 2), [(call["title"], call["page"]) for call in tmdb.search_calls])
        self.assertNotIn(("English Title", 2), [(call["title"], call["page"]) for call in tmdb.search_calls])

    def test_match_batch_parallel_results_preserve_input_order(self) -> None:
        tmdb = FakeTMDB()
        candidates = [
            self._candidate(MediaType.MOVIE, "Third.Movie.2020", candidate_id="third"),
            self._candidate(MediaType.MOVIE, "First.Movie.2020", candidate_id="first"),
            self._candidate(MediaType.MOVIE, "Second.Movie.2020", candidate_id="second"),
        ]
        hints = {}
        for candidate in candidates:
            title = candidate.display_name.replace(".", " ").replace(" 2020", "")
            hints[candidate.id] = _hint(title, year=2020, kind=TitleKind.ENGLISH, source=HintSource.LLM)
            tmdb.search_pages[(title, 2020, "en-US", 1)] = TMDBSearchPage(
                (TMDBCandidate(len(hints), MediaType.MOVIE, title, year=2020),),
                page=1,
                total_pages=1,
                total_results=1,
            )
        matcher = MatchService(
            tmdb,
            media_name_extractor=FixedMediaNameExtractor(_hint("Noisy Source")),
            llm_extractor=BatchLLMHintExtractor(hints),
        )

        results = matcher.match_batch(candidates, max_workers=3)

        self.assertEqual(list(results), ["third", "first", "second"])
        self.assertEqual([result.confidence for result in results.values()], [ConfidenceLevel.HIGH] * 3)

    def test_tv_resolution_result_validation(self) -> None:
        results = validate_results(
            ["Season 1/Ugly.mkv"],
            [
                {"filename": "Season 1/Ugly.mkv", "season": "1", "episode": "7"},
                {"filename": "Other.mkv", "season": "1", "episode": "8"},
            ],
        )

        self.assertEqual(results["Season 1/Ugly.mkv"].episode, 7)
        self.assertNotIn("Other.mkv", results)
        long_batch = validate_results(
            [str(i) for i in range(101)],
            [{"filename": "100", "season": "1", "episode": "1000"}],
        )
        self.assertEqual(long_batch["100"].episode, 1000)
        junk = validate_results(
            ["sample.mkv"],
            [{"filename": "sample.mkv", "season": -1, "episode": -1, "end_episode": None}],
        )
        self.assertEqual(junk["sample.mkv"].season, -1)

        with self.assertRaises(MatchError):
            validate_results(["A.mkv"], [{"filename": "A.mkv", "season": "x"}])

    def test_llm_prompt_assets_load_from_files(self) -> None:
        prompts = PromptSet.from_dir()

        self.assertIn("{{INPUT_JSON}}", prompts.media_match_user)
        self.assertIn("{{INPUT_JSON}}", prompts.media_match_batch_user)
        self.assertIn("{{FILENAMES_JSON}}", prompts.tv_resolution_user)
        self.assertIn('"items"', prompts.tv_resolution_system)

    def test_llm_json_parser_accepts_fenced_or_embedded_json(self) -> None:
        fenced = loads_json_from_content('```json\n{"title":"Example","year":2020}\n```')
        embedded = loads_json_from_content('Result:\n[{"filename":"A.mkv","season":1,"episode":2}]')

        self.assertEqual(fenced["title"], "Example")
        self.assertEqual(embedded[0]["episode"], 2)

    def test_media_name_hint_extractor_reads_tmdb_id_title_year_and_tags(self) -> None:
        hint = HintExtractor(TEST_MEDIA_EXTENSIONS).extract(
            self._candidate(MediaType.TV, "Example.Show.2020 {tmdb-123} #UHD#")
        )

        self.assertEqual(hint.primary_title, "Example Show")
        self.assertEqual(hint.year, 2020)
        self.assertEqual(hint.tmdb_id, 123)

    def test_tmdb_http_client_uses_media_specific_endpoints_and_multilingual_details(self) -> None:
        class FakeHTTP(TMDBHttpClient):
            def __init__(self):
                super().__init__("key")
                self.calls = []

            def _get(self, path, params=None, *, swallow_404=False):
                self.calls.append((path, dict(params or {})))
                if path == "/search/movie":
                    return {
                        "page": 1,
                        "total_pages": 1,
                        "total_results": 1,
                        "results": [
                            {
                                "id": 1,
                                "title": "Avatar",
                                "original_title": "Avatar",
                                "release_date": "2009-12-18",
                            }
                        ],
                    }
                if path == "/movie/1":
                    return {
                        "id": 1,
                        "title": "Avatar",
                        "original_title": "Avatar",
                        "release_date": "2009-12-18",
                        "genre_ids": [878],
                        "alternative_titles": {"titles": [{"title": "阿凡达", "iso_3166_1": "CN"}]},
                        "translations": {"translations": [{"iso_3166_1": "CN", "data": {"title": "阿凡达"}}]},
                    }
                raise AssertionError(path)

        client = FakeHTTP()

        search_page = client.search_page(MediaType.MOVIE, "阿凡达", 2009, "zh-CN", 1)
        self.assertEqual([path for path, _params in client.calls], ["/search/movie"])
        detail = client.load_candidate_details(MediaType.MOVIE, search_page.results[0].tmdb_id, "zh-CN", search_page.results[0])

        self.assertEqual(search_page.results[0].media_type, MediaType.MOVIE)
        self.assertEqual(search_page.results[0].title, "Avatar")
        self.assertEqual(detail.title, "阿凡达")
        self.assertIn("阿凡达", detail.known_titles())
        self.assertEqual(detail.alternative_titles[0]["iso_3166_1"], "CN")
        self.assertNotIn("/search/tv", [path for path, _params in client.calls])

    def test_tmdb_detail_prefers_native_chinese_title_before_cn_alias(self) -> None:
        class FakeHTTP(TMDBHttpClient):
            def __init__(self):
                super().__init__("key")

            def _get(self, path, params=None, *, swallow_404=False):
                return {
                    "id": 1136557,
                    "title": "Day Dreaming",
                    "original_title": "朱同在三年级丢失了超能力",
                    "original_language": "zh",
                    "release_date": "2024-05-25",
                    "alternative_titles": {
                        "titles": [
                            {"title": "漫漫长日", "iso_3166_1": "CN"},
                            {"title": "Day Dreaming", "iso_3166_1": "CN"},
                        ]
                    },
                    "translations": {"translations": [{"iso_3166_1": "CN", "data": {"title": "漫漫长日"}}]},
                }

        result = FakeHTTP().get_by_id(MediaType.MOVIE, 1136557)

        self.assertEqual(result.title, "朱同在三年级丢失了超能力")
        self.assertEqual(result.original_title, "朱同在三年级丢失了超能力")
        self.assertIn("漫漫长日", result.known_titles())
        self.assertEqual(result.metadata["preferred_title_source"], "original_title")

    def test_tmdb_detail_uses_chinese_alias_before_non_chinese_cjk_native_title(self) -> None:
        class FakeHTTP(TMDBHttpClient):
            def __init__(self):
                super().__init__("key")

            def _get(self, path, params=None, *, swallow_404=False):
                return {
                    "id": 1450115,
                    "title": "The Silent Service: The Battle of Arctic Ocean",
                    "original_title": "沈黙の艦隊 北極海大海戦",
                    "original_language": "ja",
                    "release_date": "2025-09-26",
                    "alternative_titles": {
                        "titles": [{"title": "沉默的舰队 北极海大海战", "iso_3166_1": "CN"}]
                    },
                    "translations": {"translations": []},
                }

        result = FakeHTTP().get_by_id(MediaType.MOVIE, 1450115)

        self.assertEqual(result.title, "沉默的舰队 北极海大海战")
        self.assertEqual(result.original_title, "沈黙の艦隊 北極海大海戦")
        self.assertIn("沈黙の艦隊 北極海大海戦", result.known_titles())
        self.assertEqual(result.metadata["preferred_title_source"], "alternative_titles")

    def test_tmdb_detail_keeps_localized_chinese_primary_for_non_chinese_native_title(self) -> None:
        class FakeHTTP(TMDBHttpClient):
            def __init__(self):
                super().__init__("key")

            def _get(self, path, params=None, *, swallow_404=False):
                return {
                    "id": 1450115,
                    "title": "沉默的舰队 北极海大海战",
                    "original_title": "沈黙の艦隊 北極海大海戦",
                    "original_language": "ja",
                    "release_date": "2025-09-26",
                    "alternative_titles": {"titles": [{"title": "静默舰队", "iso_3166_1": "CN"}]},
                    "translations": {"translations": []},
                }

        result = FakeHTTP().get_by_id(MediaType.MOVIE, 1450115)

        self.assertEqual(result.title, "沉默的舰队 北极海大海战")
        self.assertEqual(result.metadata["preferred_title_source"], "primary")

    def test_tmdb_direct_lookup_prefers_cn_then_sg_chinese_titles(self) -> None:
        class FakeHTTP(TMDBHttpClient):
            def __init__(self):
                super().__init__("key")
                self.calls = []

            def _get(self, path, params=None, *, swallow_404=False):
                self.calls.append((path, dict(params or {})))
                return {
                    "id": 1,
                    "name": "English Title",
                    "original_name": "Original Title",
                    "first_air_date": "2020-01-01",
                    "alternative_titles": {
                        "results": [
                            {"title": "新加坡标题", "iso_3166_1": "SG"},
                            {"title": "中国标题", "iso_3166_1": "CN"},
                        ]
                    },
                    "translations": {"translations": [{"iso_3166_1": "CN", "data": {"name": "翻译标题"}}]},
                }

        client = FakeHTTP()

        result = client.get_by_id(MediaType.TV, 1)

        self.assertEqual(result.title, "中国标题")
        self.assertEqual(result.metadata["preferred_title_source"], "alternative_titles")
        self.assertEqual(client.calls[0][1]["language"], "zh-CN")

    def test_tmdb_direct_lookup_uses_cn_translation_when_alias_missing(self) -> None:
        class FakeHTTP(TMDBHttpClient):
            def __init__(self):
                super().__init__("key")

            def _get(self, path, params=None, *, swallow_404=False):
                return {
                    "id": 1,
                    "name": "English Title",
                    "original_name": "Original Title",
                    "first_air_date": "2020-01-01",
                    "alternative_titles": {"results": [{"title": "English Alias", "iso_3166_1": "US"}]},
                    "translations": {"translations": [{"iso_3166_1": "CN", "data": {"name": "中文译名"}}]},
                }

        result = FakeHTTP().get_by_id(MediaType.TV, 1)

        self.assertEqual(result.title, "中文译名")
        self.assertEqual(result.metadata["preferred_title_source"], "translations")

    def test_tmdb_direct_lookup_keeps_english_when_no_chinese_title_exists(self) -> None:
        class FakeHTTP(TMDBHttpClient):
            def __init__(self):
                super().__init__("key")

            def _get(self, path, params=None, *, swallow_404=False):
                return {
                    "id": 1,
                    "title": "English Title",
                    "original_title": "Original Title",
                    "release_date": "2020-01-01",
                    "alternative_titles": {"results": [{"title": "English Alias", "iso_3166_1": "US"}]},
                    "translations": {"translations": []},
                }

        result = FakeHTTP().get_by_id(MediaType.MOVIE, 1)

        self.assertEqual(result.title, "English Title")
        self.assertEqual(result.metadata["preferred_title_source"], "primary")

    @unittest.skipIf(OPENCC_CONVERTER is None, "OpenCC is not installed")
    def test_tmdb_direct_lookup_converts_traditional_chinese_title(self) -> None:
        class FakeHTTP(TMDBHttpClient):
            def __init__(self):
                super().__init__("key")

            def _get(self, path, params=None, *, swallow_404=False):
                return {
                    "id": 1,
                    "name": "後宮甄嬛傳",
                    "original_name": "後宮甄嬛傳",
                    "first_air_date": "2011-01-01",
                    "alternative_titles": {"results": []},
                    "translations": {"translations": []},
                }

        result = FakeHTTP().get_by_id(MediaType.TV, 1)

        self.assertEqual(result.title, "后宫甄嬛传")
    def _candidate(
        self,
        media_type: MediaType,
        display_name: str,
        *,
        files: tuple[str, ...] = (),
        structure: str | None = None,
        candidate_id: str = "candidate",
    ) -> MediaCandidate:
        candidate_path = Path("source") / display_name
        return MediaCandidate(
            id=candidate_id,
            media_type=media_type,
            source_root=Path("source"),
            candidate_path=candidate_path,
            display_name=display_name,
            files=[
                MediaFile(
                    path=candidate_path / relative_path,
                    relative_path=Path(relative_path),
                    extension=(candidate_path / relative_path).suffix.lower(),
                )
                for relative_path in files
            ],
            structure=structure,
        )


if __name__ == "__main__":
    unittest.main()

