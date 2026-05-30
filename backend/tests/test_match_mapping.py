from __future__ import annotations

import unittest
from pathlib import Path

from app.services.identify.match import MatchService
from app.services.identify.preview import build_candidate_preview
from app.domain.match import ConfidenceLevel, MatchEvidence
from app.domain.media import MediaType
from app.domain.origin import OrganizePolicy
from app.domain.match import HintSource, MatchHint, TMDBCandidate, TitleHint, TitleKind
from app.domain.media import MediaCandidate
from app.engines.match.hint import HintExtractor
from app.engines.plan.tv.parser import TVParseConfidence, extract_episode_info
from app.services.identify.evidence import (
    MATCH_EVIDENCE_SUMMARY_KEY,
    MatchEvidenceSummary,
    match_evidence_from_payload,
    match_evidence_payload,
    match_evidence_summaries,
    match_evidence_summary_payload,
    match_evidence_view_payload,
)
from support import FakeTMDB, FixedLLMHintExtractor, TEST_MEDIA_EXTENSIONS


class MatchMappingTests(unittest.TestCase):
    def test_filename_tmdb_id_direct_lookup_preserves_high_confidence(self) -> None:
        tmdb = FakeTMDB()
        tmdb.by_id[(MediaType.MOVIE, 19995)] = TMDBCandidate(19995, MediaType.MOVIE, "Avatar", year=2009)
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                MatchHint(
                    titles=(TitleHint("Source Movie", TitleKind.ENGLISH, HintSource.LLM),),
                    year=2020,
                )
            ),
        )

        result = matcher.match(self._candidate(MediaType.MOVIE, "Avatar (2009) {tmdb-19995}.mkv"))
        candidate = self._organize_candidate(result)

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(candidate.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(candidate.metadata["tmdb_id"], 19995)

    def test_llm_tmdb_search_path_preserves_high_confidence(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_results = [TMDBCandidate(7, MediaType.TV, "Example Show", year=2020)]
        matcher = MatchService(
            tmdb,
            llm_extractor=FixedLLMHintExtractor(
                MatchHint(
                    titles=(TitleHint("Example Show", TitleKind.ENGLISH, HintSource.LLM),),
                    year=2020,
                )
            ),
        )

        result = matcher.match(self._candidate(MediaType.TV, "Example.Show.S01E01.mkv"))
        candidate = self._organize_candidate(result)

        self.assertEqual(candidate.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.tmdb_id, 7)
        self.assertIn("llm_hint", [item["source"] for item in candidate.evidence["summary"]])

    def test_non_high_confidence_result_preserves_confidence_with_metadata(self) -> None:
        tmdb = FakeTMDB()
        tmdb.search_results = [TMDBCandidate(1, MediaType.MOVIE, "Different Movie", year=2020)]
        matcher = MatchService(
            tmdb,
            media_name_extractor=HintExtractor(TEST_MEDIA_EXTENSIONS),
            llm_extractor=FixedLLMHintExtractor(
                MatchHint(
                    titles=(TitleHint("Source Movie", TitleKind.ENGLISH, HintSource.LLM),),
                    year=2020,
                )
            ),
        )

        result = matcher.match(self._candidate(MediaType.MOVIE, "Source.Movie.2020.mkv"))
        candidate = self._organize_candidate(result)

        self.assertNotEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(candidate.confidence, result.confidence)
        self.assertEqual(candidate.metadata["tmdb_id"], 1)

    def test_tv_episode_parser_returns_field_level_result(self) -> None:
        result = extract_episode_info("Example.Show.S02E07.mkv")

        self.assertEqual(result.season, 2)
        self.assertEqual(result.episode, 7)
        self.assertIsNone(result.end_episode)
        self.assertEqual(result.season_confidence, TVParseConfidence.EXPLICIT)
        self.assertEqual(result.episode_confidence, TVParseConfidence.EXPLICIT)

    def test_match_evidence_payload_round_trips_through_owner_accessors(self) -> None:
        payload = match_evidence_payload(
            [
                MatchEvidence(
                    source="llm_hint",
                    confidence=ConfidenceLevel.HIGH,
                    values={"title": "Example Show"},
                    reason="accepted",
                )
            ]
        )

        self.assertEqual(payload[MATCH_EVIDENCE_SUMMARY_KEY][0]["source"], "llm_hint")
        self.assertEqual(match_evidence_summary_payload(payload)[0]["values"]["title"], "Example Show")
        summaries = match_evidence_summaries(payload)
        self.assertIsNotNone(summaries)
        self.assertIsInstance(summaries[0], MatchEvidenceSummary)
        self.assertEqual(summaries[0].values["title"], "Example Show")

        restored = match_evidence_from_payload(payload, fallback_confidence=ConfidenceLevel.LOW)
        self.assertEqual(restored[0].source, "llm_hint")
        self.assertEqual(restored[0].confidence, ConfidenceLevel.HIGH)
        self.assertEqual(restored[0].values["title"], "Example Show")

    def test_match_evidence_payload_tolerates_malformed_summary(self) -> None:
        payload = {MATCH_EVIDENCE_SUMMARY_KEY: [{"source": "", "confidence": "unknown", "values": "bad"}, "bad"]}

        restored = match_evidence_from_payload(payload, fallback_confidence=ConfidenceLevel.MEDIUM)

        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0].source, "candidate_match")
        self.assertEqual(restored[0].confidence, ConfidenceLevel.MEDIUM)
        self.assertEqual(restored[0].values, {})

    def test_match_evidence_view_payload_normalizes_summary_and_preserves_other_keys(self) -> None:
        payload = {
            MATCH_EVIDENCE_SUMMARY_KEY: [
                {"source": "llm_hint", "confidence": "high", "values": {"title": "Example Show"}},
                "bad",
            ],
            "movie_plan": {"media_kind": "primary"},
        }

        projected = match_evidence_view_payload(payload)

        self.assertIsNot(projected, payload)
        self.assertEqual(projected["movie_plan"], payload["movie_plan"])
        self.assertEqual(projected[MATCH_EVIDENCE_SUMMARY_KEY][0]["source"], "llm_hint")
        self.assertEqual(projected[MATCH_EVIDENCE_SUMMARY_KEY][0]["values"]["title"], "Example Show")
        self.assertEqual(len(projected[MATCH_EVIDENCE_SUMMARY_KEY]), 1)

    def _candidate(self, media_type: MediaType, name: str) -> MediaCandidate:
        return MediaCandidate(
            id=name,
            media_type=media_type,
            source_root=Path("source"),
            candidate_path=Path(name),
            display_name=Path(name).stem,
        )

    def _organize_candidate(self, result):
        return build_candidate_preview(
            source_candidate_id=result.candidate_id,
            source_file_id=f"{result.candidate_id}:file",
            item_id=f"{result.candidate_id}:item",
            source_path=Path("source") / f"{result.candidate_id}",
            source_root=Path("source"),
            match_result=result,
            policy=OrganizePolicy(target_depot_id="Depot"),
        )


if __name__ == "__main__":
    unittest.main()
