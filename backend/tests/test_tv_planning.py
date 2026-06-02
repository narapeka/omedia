from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path

from app.domain.match import ConfidenceLevel
from app.domain.media import MediaType
from app.domain.origin import OrganizePolicy
from app.domain.match import TVYearFactSource, TVYearScope
from app.domain.tv import EpisodeLLMResult, TVEpisodeCatalog, TVEpisodeFile, TVShowIdentity, format_episode_catalog_for_prompt
from app.engines.match.context import derive_tv_source_context
from app.engines.name.renderer import TVNamingInput, render_tv_path
from app.engines.name.tv.source import extract_last_tag, extract_season_number
from app.engines.plan.tv.parser import (
    TVParseConfidence,
    extract_episode_info,
)
from app.engines.plan.tv.resolution import (
    TVResolutionStatus,
    resolve_tv_episode_segment,
)
from app.engines.plan.tv.catalog import episode_title_from_metadata
from app.engines.plan.tv.planner import (
    TVEpisodePlanner,
    plan_episode_files,
)
from app.services.identify.preview import Preview
from app.engines.scan.source import scan_tv_root
from app.domain.match import MatchResult
from support import FakeTVEpisodeCatalogProvider, FakeTVEpisodeExtractor, TEST_MEDIA_EXTENSIONS


class TVPlanningTests(unittest.TestCase):
    def test_tv_package_does_not_export_implementation(self) -> None:
        tv = importlib.import_module("app.engines.plan.tv")

        self.assertFalse(hasattr(tv, "__all__"))
        self.assertNotIn("extract_episode_info", vars(tv))
        self.assertNotIn("plan_episode_files", vars(tv))

    def test_parser_handles_current_episode_patterns(self) -> None:
        cases = {
            "S01E02.mkv": (1, 2, None),
            "S01E01-E03.mkv": (1, 1, 3),
            "Example Show - 2x07.mkv": (2, 7, None),
            "E04.srt": (1, 4, None),
            "Special.S00E01.mkv": (0, 1, None),
        }

        for filename, expected in cases.items():
            with self.subTest(filename=filename):
                parsed = extract_episode_info(filename)
                self.assertEqual((parsed.season, parsed.episode, parsed.end_episode), expected)

        self.assertEqual(extract_season_number("Season 2", fallback=None, mode="folder"), 2)
        self.assertEqual(extract_season_number("S03", fallback=None, mode="folder"), 3)

    def test_positive_patterns_do_not_need_metadata_blacklists(self) -> None:
        for value in [
            "Show.AAC5.1",
            "Show.TrueHD7.1.4",
            "Show.DTS-HDMA5.1",
            "Show.11Audios",
            "Show.24小时",
            "Show.1080p.x265",
        ]:
            with self.subTest(value=value):
                self.assertIsNone(extract_season_number(value, fallback=None, mode="folder"))

        parsed = extract_episode_info("S01E01-S01E03.mkv")
        self.assertEqual((parsed.season, parsed.episode, parsed.end_episode), (1, 1, 3))
        self.assertEqual(parsed.range_confidence, TVParseConfidence.EXPLICIT)

    def test_tv_resolution_merges_ambiguous_fields_and_chunks_requests(self) -> None:
        parser_results = {
            "Ugly.mkv": extract_episode_info("Ugly.mkv"),
            "Other.mkv": extract_episode_info("Other.mkv"),
            "S01E01.mkv": extract_episode_info("S01E01.mkv"),
        }
        extractor = FakeTVEpisodeExtractor(
            {
                "Ugly.mkv": EpisodeLLMResult("Ugly.mkv", 2, 7),
                "Other.mkv": EpisodeLLMResult("Other.mkv", 2, 8),
                "S01E01.mkv": EpisodeLLMResult("S01E01.mkv", 1, 101),
            }
        )

        resolved = resolve_tv_episode_segment(
            parser_results,
            request_keys=["Ugly.mkv", "Other.mkv", "S01E01.mkv"],
            show_name="Example",
            tmdb_context="",
            catalog=TVEpisodeCatalog.empty(),
            extractor=extractor,
            chunk_size=1,
        )

        self.assertEqual((resolved.merged_results["Ugly.mkv"].season, resolved.merged_results["Ugly.mkv"].episode), (2, 7))
        self.assertEqual((resolved.merged_results["Other.mkv"].season, resolved.merged_results["Other.mkv"].episode), (2, 8))
        self.assertEqual((resolved.merged_results["S01E01.mkv"].season, resolved.merged_results["S01E01.mkv"].episode), (1, 1))
        self.assertEqual([call["filenames"] for call in extractor.calls], [["Ugly.mkv"], ["Other.mkv"]])
        self.assertEqual(resolved.requested_keys, ["Ugly.mkv", "Other.mkv"])

    def test_tv_naming_tag_specials_and_multi_episode(self) -> None:
        tag = extract_last_tag("Example Show #1080p# #UHD#")
        show = TVShowIdentity("Example Show #UHD#", title="Example: Show", year=2020, tmdb_id=123, tag=tag)
        episode = self._episode_file(Path("S00E01-E02.mkv"), 0, 1, 2, True)
        episode.title = "Pilot: Part 1-Pilot: Part 2"
        rendered = render_tv_path(
            TVNamingInput(
                title=show.title or show.source_name,
                year=show.year,
                tmdb_id=show.tmdb_id,
                season=episode.season_number,
                episode=episode.episode_number,
                end_episode=episode.end_episode_number,
                episode_title=episode.title,
                extension=episode.extension or episode.source_path.suffix,
                tag_suffix=show.tag.rendered_suffix if show.tag else None,
            )
        )

        self.assertEqual(tag.raw_tag, "UHD")
        self.assertEqual(rendered.relative_path.parts[0], "Example. Show (2020) {tmdb-123} [UHD]")
        self.assertEqual(rendered.relative_path.parts[1], "Specials")
        self.assertEqual(rendered.relative_path.name, "Example. Show - S00E01-E02 - Pilot. Part 1-Pilot. Part 2.mkv")

    def test_subtitle_sidecar_plans_beside_episode(self) -> None:
        show = TVShowIdentity("Example", title="Example", year=2020, tmdb_id=1)
        subtitle = self._episode_file(Path("S01E01.srt"), 1, 1, confident=True)

        rendered = render_tv_path(
            TVNamingInput(
                title=show.title or show.source_name,
                year=show.year,
                tmdb_id=show.tmdb_id,
                season=subtitle.season_number,
                episode=subtitle.episode_number,
                episode_title=subtitle.title,
                extension=subtitle.extension or subtitle.source_path.suffix,
            )
        )
        destination = Path("Depot") / rendered.relative_path

        self.assertTrue(subtitle.is_sidecar)
        self.assertEqual(destination, Path("Depot/Example (2020) {tmdb-1}/Season 1/Example - S01E01.srt"))

    def test_tmdb_episode_catalog_uses_boundary_titles(self) -> None:
        catalog = TVEpisodeCatalog({1: {1: "One", 2: "Two", 3: "Three"}})

        self.assertEqual(catalog.titles_for_range(1, 1, None), "One")
        self.assertEqual(catalog.titles_for_range(1, 1, 1), "One")
        self.assertEqual(catalog.titles_for_range(1, 1, 3), "One-Three")

    def test_episode_title_metadata_parsing_uses_tv_catalog_owner(self) -> None:
        metadata = {
            "episode_titles": {"2": {"7": "Mapped Title"}},
            "episodes": [{"season_number": "2", "episode_number": "8", "name": "List Title"}],
        }

        self.assertEqual(episode_title_from_metadata(metadata, 2, 7), "Mapped Title")
        self.assertEqual(episode_title_from_metadata(metadata, 2, 8), "List Title")
        self.assertIsNone(episode_title_from_metadata(metadata, None, 8))

    def test_tmdb_catalog_boundary_titles_flow_through_preview_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._materialize_tree(root, {"Example.Show": ["S01E01-E03.mkv"]})
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]
            service = TVEpisodePlanner(
                extensions=TEST_MEDIA_EXTENSIONS,
                episode_extractor=FakeTVEpisodeExtractor(),
                episode_catalog_provider=FakeTVEpisodeCatalogProvider(
                    TVEpisodeCatalog({1: {1: "One", 2: "Two", 3: "Three"}})
                ),
            )

            previews = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=self._match_result(media_candidate.id),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
                tv_episode_planner=service,
            )

            self.assertEqual(previews[0].evidence["tv_episode_plan"]["episode_title"], "One-Three")
            self.assertEqual(
                previews[0].preview.proposed_relative_path,
                Path("Example Show (2020) {tmdb-1}/Season 1/Example Show - S01E01-E03 - One-Three.mkv"),
            )

    def test_tv_planner_uses_scoped_episode_titles_for_parser_resolved_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._materialize_tree(root, {"Example.Show": ["S01E01.mkv"]})
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]
            provider = _ScopedTitleProvider({1: {1: "Pilot"}})
            service = TVEpisodePlanner(
                extensions=TEST_MEDIA_EXTENSIONS,
                episode_extractor=FakeTVEpisodeExtractor(),
                episode_catalog_provider=provider,
            )

            previews = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=self._match_result(media_candidate.id),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
                tv_episode_planner=service,
            )

            self.assertEqual(provider.catalog_calls, [])
            self.assertEqual(provider.title_calls, [(1, (1,))])
            self.assertEqual(previews[0].evidence["tv_episode_plan"]["episode_title"], "Pilot")

    def test_tv_episode_catalog_formats_prompt_context(self) -> None:
        catalog = TVEpisodeCatalog({0: {1: "Special"}, 1: {1: "Pilot", 2: "Second"}})

        self.assertEqual(
            format_episode_catalog_for_prompt(catalog),
            "Official TMDB Episode List:\n"
            "Season 0:\n"
            "  - Episode 1: Special\n"
            "Season 1:\n"
            "  - Episode 1: Pilot\n"
            "  - Episode 2: Second",
        )

    def test_direct_file_planner_uses_folder_context_and_explicit_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._materialize_tree(
                root,
                {
                    "The.Outcast.S02": ["E01.mkv", "E04.srt", "S03E02.mkv", "S03E02.nfo", "S00E03.mkv"],
                    "Example.S101": ["E01.mkv"],
                },
            )

            candidates = {candidate.display_name: candidate for candidate in scan_tv_root(root, TEST_MEDIA_EXTENSIONS)}
            outcast = self._planned_by_source(candidates["The.Outcast.S02"])
            high_season = self._planned_by_source(candidates["Example.S101"])

            self.assertEqual(outcast["E01.mkv"], (2, 1, False))
            self.assertEqual(outcast["E04.srt"], (2, 4, True))
            self.assertEqual(outcast["S03E02.mkv"], (3, 2, False))
            self.assertEqual(outcast["S00E03.mkv"], (0, 3, False))
            self.assertNotIn("S03E02.nfo", outcast)
            self.assertEqual(high_season["E01.mkv"], (101, 1, False))

    def test_subfolder_and_mixed_planner_uses_folder_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._materialize_tree(
                root,
                {
                    "Example.Show": {
                        "S03": ["S02E01.mkv", "S03E03.srt", "S04E02.mkv"],
                        "alpha": ["NoEpisodeName.mkv"],
                        "beta": ["NoEpisodeName.mkv"],
                        "Season 0": ["S00E01.mkv"],
                    },
                    "Mixed.Show": {
                        "E01.mkv": None,
                        "Season 2": ["E01.mkv"],
                    },
                },
            )

            candidates = {candidate.display_name: candidate for candidate in scan_tv_root(root, TEST_MEDIA_EXTENSIONS)}
            planned = self._planned_by_source(candidates["Example.Show"])
            mixed = self._planned_by_source(candidates["Mixed.Show"])

            self.assertEqual(planned["S03/S02E01.mkv"], (3, 1, False))
            self.assertEqual(planned["S03/S03E03.srt"], (3, 3, True))
            self.assertEqual(planned["S03/S04E02.mkv"], (3, 2, False))
            self.assertEqual(planned["alpha/NoEpisodeName.mkv"], (1, 1, False))
            self.assertEqual(planned["beta/NoEpisodeName.mkv"], (2, 1, False))
            self.assertEqual(planned["Season 0/S00E01.mkv"], (0, 1, False))
            self.assertEqual(mixed["E01.mkv"], (1, 1, False))
            self.assertEqual(mixed["Season 2/E01.mkv"], (2, 1, False))

    def test_tv_match_context_derives_scoped_year_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._materialize_tree(
                root,
                {
                    "Direct.Show.S02.2022": ["E01.mkv"],
                    "Ordinary.Show.2020": ["E01.mkv"],
                    "Seasoned.Show": {
                        "Season 2 2022": ["E01.mkv"],
                        "2023": ["E02.mkv"],
                    },
                    "Mixed.Show.S02.2022": {
                        "E01.mkv": None,
                        "Season 3 2023": ["E01.mkv"],
                    },
                    "Special.Show.S00.2022": ["E01.mkv"],
                },
            )

            candidates = {candidate.display_name: candidate for candidate in scan_tv_root(root, TEST_MEDIA_EXTENSIONS)}
            direct = derive_tv_source_context(candidates["Direct.Show.S02.2022"], TEST_MEDIA_EXTENSIONS)
            ordinary = derive_tv_source_context(candidates["Ordinary.Show.2020"], TEST_MEDIA_EXTENSIONS)
            seasoned = derive_tv_source_context(candidates["Seasoned.Show"], TEST_MEDIA_EXTENSIONS)
            mixed = derive_tv_source_context(candidates["Mixed.Show.S02.2022"], TEST_MEDIA_EXTENSIONS)
            special = derive_tv_source_context(candidates["Special.Show.S00.2022"], TEST_MEDIA_EXTENSIONS)

            self.assertEqual(direct.show_title_source, "Direct Show")
            self.assertEqual((direct.year_facts[0].scope, direct.year_facts[0].year, direct.year_facts[0].season), (TVYearScope.SHOW_OR_SEASON_YEAR, 2022, 2))
            self.assertEqual((ordinary.show_title_source, ordinary.year_facts[0].scope, ordinary.year_facts[0].year), ("Ordinary Show", TVYearScope.SHOW_YEAR, 2020))
            self.assertEqual((seasoned.show_title_source, len(seasoned.year_facts)), ("Seasoned Show", 1))
            self.assertEqual((seasoned.year_facts[0].scope, seasoned.year_facts[0].year, seasoned.year_facts[0].season), (TVYearScope.SEASON_YEAR, 2022, 2))
            self.assertEqual(
                [(fact.scope, fact.source, fact.year, fact.season) for fact in mixed.year_facts],
                [
                    (TVYearScope.SHOW_OR_SEASON_YEAR, TVYearFactSource.DIRECT_ROOT_SEGMENT, 2022, 2),
                    (TVYearScope.SEASON_YEAR, TVYearFactSource.SEASON_SUBFOLDER, 2023, 3),
                ],
            )
            self.assertEqual(special.detected_seasons, (0,))
            self.assertEqual(special.year_facts[0].season, 0)

    def test_tv_resolution_core_handles_guards_errors_junk_and_catalog_validation(self) -> None:
        parser_results = {
            "A.mkv": extract_episode_info("A.mkv"),
            "S01E02.mkv": extract_episode_info("S01E02.mkv"),
        }
        extractor = FakeTVEpisodeExtractor(
            {
                "A.mkv": {"season": 2, "episode": 7, "end_episode": None},
                "S01E02.mkv": {"season": 2, "episode": 8, "end_episode": None},
                "Junk.mkv": {"season": -1, "episode": -1, "end_episode": None},
                "BadRange.mkv": {"season": 1, "episode": 9, "end_episode": 7},
                "MissingCatalog.mkv": {"season": 3, "episode": 1, "end_episode": None},
            }
        )
        catalog = TVEpisodeCatalog({1: {1: "One", 2: "Two"}, 2: {7: "Seven", 8: "Eight"}})

        applied = resolve_tv_episode_segment(
            parser_results,
            request_keys=["A.mkv", "S01E02.mkv"],
            show_name="Example",
            tmdb_context="Official TMDB Episode List:",
            catalog=catalog,
            extractor=extractor,
        )
        self.assertEqual((applied.merged_results["A.mkv"].season, applied.merged_results["A.mkv"].episode), (2, 7))
        self.assertEqual((applied.merged_results["S01E02.mkv"].season, applied.merged_results["S01E02.mkv"].episode), (1, 2))
        self.assertEqual(applied.applied_keys, ["A.mkv"])

        not_needed = resolve_tv_episode_segment(
            {"S01E02.mkv": extract_episode_info("S01E02.mkv")},
            request_keys=["S01E02.mkv"],
            show_name="Example",
            tmdb_context="",
            catalog=TVEpisodeCatalog.empty(),
            extractor=extractor,
        )
        error = resolve_tv_episode_segment(
            parser_results,
            request_keys=["A.mkv", "S01E02.mkv"],
            show_name="Example",
            tmdb_context="",
            catalog=TVEpisodeCatalog.empty(),
            extractor=FakeTVEpisodeExtractor(error=RuntimeError("boom")),
        )
        empty = resolve_tv_episode_segment(
            parser_results,
            request_keys=["A.mkv", "S01E02.mkv"],
            show_name="Example",
            tmdb_context="",
            catalog=TVEpisodeCatalog.empty(),
            extractor=FakeTVEpisodeExtractor(),
        )
        junk = resolve_tv_episode_segment(
            {"Junk.mkv": extract_episode_info("Junk.mkv")},
            request_keys=["Junk.mkv"],
            show_name="Example",
            tmdb_context="",
            catalog=TVEpisodeCatalog.empty(),
            extractor=extractor,
        )
        rejected = resolve_tv_episode_segment(
            {
                "BadRange.mkv": extract_episode_info("BadRange.mkv"),
                "MissingCatalog.mkv": extract_episode_info("MissingCatalog.mkv"),
            },
            request_keys=["BadRange.mkv", "MissingCatalog.mkv"],
            show_name="Example",
            tmdb_context="Official TMDB Episode List:",
            catalog=catalog,
            extractor=extractor,
        )

        self.assertEqual(not_needed.status, TVResolutionStatus.NOT_NEEDED)
        self.assertEqual(error.status, TVResolutionStatus.ERROR)
        self.assertEqual(empty.status, TVResolutionStatus.ATTEMPTED)
        self.assertEqual(junk.junk_keys, ["Junk.mkv"])
        self.assertIn("invalid episode range", rejected.warning or "")
        self.assertIn("not present in TMDB catalog", rejected.warning or "")

    def test_subtitle_inherits_llm_corrected_video_context_without_resolution_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._materialize_tree(root, {"Example.Show": ["UglyNameA.mkv", "UglyNameA.zh.srt"]})
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]
            extractor = FakeTVEpisodeExtractor(
                {"UglyNameA.mkv": {"season": 2, "episode": 7, "end_episode": None}}
            )
            service = TVEpisodePlanner(
                extensions=TEST_MEDIA_EXTENSIONS,
                episode_extractor=extractor,
                episode_catalog_provider=FakeTVEpisodeCatalogProvider(TVEpisodeCatalog({2: {7: "Corrected"}})),
            )

            previews = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=self._match_result(media_candidate.id),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
                tv_episode_planner=service,
            )

            by_name = {item.source_path.name: item for item in previews}
            self.assertEqual(extractor.requested_keys, ["UglyNameA.mkv"])
            self.assertEqual(
                by_name["UglyNameA.mkv"].preview.proposed_relative_path,
                Path("Example Show (2020) {tmdb-1}/Season 2/Example Show - S02E07 - Corrected.mkv"),
            )
            self.assertEqual(
                by_name["UglyNameA.zh.srt"].preview.proposed_relative_path,
                Path("Example Show (2020) {tmdb-1}/Season 2/Example Show - S02E07 - Corrected.srt"),
            )
            subtitle_evidence = by_name["UglyNameA.zh.srt"].evidence["tv_episode_plan"]
            self.assertEqual(subtitle_evidence["media_kind"], "subtitle")
            self.assertEqual(subtitle_evidence["resolution"]["status"], "applied")
            self.assertEqual(subtitle_evidence["inherited_from"], "UglyNameA.mkv")

    def test_mixed_folder_resolution_segments_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._materialize_tree(
                root,
                {
                    "Example.Show": {
                        "UglyDirect.mkv": None,
                        "Season 2": ["UglySub.mkv"],
                    }
                },
            )
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]
            extractor = FakeTVEpisodeExtractor(
                {
                    "UglyDirect.mkv": {"season": 1, "episode": 3, "end_episode": None},
                    "Season 2/UglySub.mkv": {"season": 2, "episode": 7, "end_episode": None},
                }
            )
            service = TVEpisodePlanner(
                extensions=TEST_MEDIA_EXTENSIONS,
                episode_extractor=extractor,
                episode_catalog_provider=FakeTVEpisodeCatalogProvider(TVEpisodeCatalog({1: {3: "Direct"}, 2: {7: "Sub"}})),
            )

            previews = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=self._match_result(media_candidate.id),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
                tv_episode_planner=service,
            )

            self.assertEqual([call["filenames"] for call in extractor.calls], [["UglyDirect.mkv"], ["Season 2/UglySub.mkv"]])
            by_source = {
                item.source_path.relative_to(media_candidate.candidate_path).as_posix(): item.evidence["tv_episode_plan"]
                for item in previews
            }
            self.assertEqual((by_source["UglyDirect.mkv"]["season"], by_source["UglyDirect.mkv"]["episode"]), (1, 3))
            self.assertEqual((by_source["Season 2/UglySub.mkv"]["season"], by_source["Season 2/UglySub.mkv"]["episode"]), (2, 7))

    def test_tv_plan_evidence_records_parser_error_and_junk_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._materialize_tree(root, {"Parser.Only": ["S01E01.mkv"]})
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]

            parser_only = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=self._match_result(media_candidate.id),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
                tv_episode_planner=TVEpisodePlanner(
                    extensions=TEST_MEDIA_EXTENSIONS,
                    episode_extractor=FakeTVEpisodeExtractor(),
                    episode_catalog_provider=FakeTVEpisodeCatalogProvider(TVEpisodeCatalog({1: {1: "Pilot"}})),
                ),
            )[0]
            self.assertEqual(parser_only.evidence["tv_episode_plan"]["resolution"]["status"], "not_needed")
            self.assertEqual(parser_only.evidence["tv_episode_plan"]["episode_title"], "Pilot")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._materialize_tree(root, {"Fallback.Error": ["UglyNameA.mkv"]})
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]

            error_candidate = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=self._match_result(media_candidate.id),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
                tv_episode_planner=TVEpisodePlanner(
                    extensions=TEST_MEDIA_EXTENSIONS,
                    episode_extractor=FakeTVEpisodeExtractor(error=RuntimeError("boom")),
                    episode_catalog_provider=FakeTVEpisodeCatalogProvider(TVEpisodeCatalog({1: {1: "Parser Title"}})),
                ),
            )[0]
            resolution = error_candidate.evidence["tv_episode_plan"]["resolution"]
            self.assertEqual(resolution["status"], "error")
            self.assertIn("boom", resolution["warning"])

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._materialize_tree(root, {"Junk.Mixed": ["UglyNameA.mkv", "UglyNameB.mkv"]})
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]

            previews = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=self._match_result(media_candidate.id),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
                tv_episode_planner=TVEpisodePlanner(
                    extensions=TEST_MEDIA_EXTENSIONS,
                    episode_extractor=FakeTVEpisodeExtractor(
                        {
                            "UglyNameA.mkv": {"season": -1, "episode": -1, "end_episode": None},
                            "UglyNameB.mkv": {"season": 1, "episode": 2, "end_episode": None},
                        }
                    ),
                    episode_catalog_provider=FakeTVEpisodeCatalogProvider(TVEpisodeCatalog({1: {2: "Kept"}})),
                ),
            )
            by_name = {item.source_path.name: item for item in previews}
            self.assertNotIn("UglyNameA.mkv", by_name)
            self.assertEqual(by_name["UglyNameB.mkv"].evidence["tv_episode_plan"]["resolution"]["junk_keys"], ["UglyNameA.mkv"])

    def test_preview_deduplicates_tv_subtitles_and_excludes_generic_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            show = root / "Example.Show.S02"
            show.mkdir()
            for name in [
                "E01.mkv",
                "E01.srt",
                "E01.zh.srt",
                "E01.sup",
                "E02.b.srt",
                "E02.a.srt",
                "E01.nfo",
                "poster.jpg",
            ]:
                (show / name).write_text("x", encoding="utf-8")
            media_candidate = scan_tv_root(root, TEST_MEDIA_EXTENSIONS)[0]

            previews = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=root,
                match_result=self._match_result(media_candidate.id),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )

            by_source = {item.source_path.name: item for item in previews}
            self.assertEqual(set(by_source), {"E01.mkv", "E01.zh.srt", "E01.sup", "E02.a.srt"})
            self.assertNotIn("E01.srt", by_source)
            self.assertNotIn("E01.nfo", by_source)
            self.assertNotIn("poster.jpg", by_source)
            destinations = [item.preview.proposed_relative_path.as_posix() for item in previews]
            self.assertEqual(len(destinations), len(set(destinations)))
            self.assertEqual(
                by_source["E01.zh.srt"].preview.proposed_relative_path,
                Path("Example Show (2020) {tmdb-1}/Season 2/Example Show - S02E01.srt"),
            )
            self.assertEqual(
                by_source["E01.sup"].preview.proposed_relative_path,
                Path("Example Show (2020) {tmdb-1}/Season 2/Example Show - S02E01.sup"),
            )
            self.assertEqual(
                by_source["E01.zh.srt"].evidence["tv_episode_plan"]["media_kind"],
                "subtitle",
            )
            self.assertEqual(
                by_source["E01.zh.srt"].evidence["tv_episode_plan"]["ignored_duplicate_subtitles"],
                ["E01.srt"],
            )

    def _planned_by_source(self, media_candidate):
        planned_by_path = {
            planned.source_path: planned
            for planned in plan_episode_files(
                media_candidate,
                extensions=TEST_MEDIA_EXTENSIONS,
                include_subtitles=True,
            )
        }
        result = {}
        for file in media_candidate.files:
            planned = planned_by_path.get(file.path)
            if planned is not None:
                result[file.relative_path.as_posix()] = (
                    planned.season_number,
                    planned.episode_number,
                    planned.is_sidecar,
                )
        return result

    def _match_result(self, candidate_id: str) -> MatchResult:
        return MatchResult(
            candidate_id=candidate_id,
            media_type=MediaType.TV,
            confidence=ConfidenceLevel.HIGH,
            title="Example Show",
            year=2020,
            tmdb_id=1,
            metadata={"title": "Example Show", "release_year": 2020, "tmdb_id": 1},
        )

    def _episode_file(
        self,
        source_path: Path,
        season: int,
        episode: int,
        end_episode: int | None = None,
        confident: bool = False,
    ) -> TVEpisodeFile:
        suffix = source_path.suffix.lower()
        return TVEpisodeFile(
            source_path=source_path,
            season_number=season,
            episode_number=episode,
            end_episode_number=end_episode,
            extension=source_path.suffix,
            is_sidecar=suffix in TEST_MEDIA_EXTENSIONS.sidecar_like,
            media_kind="subtitle" if suffix in TEST_MEDIA_EXTENSIONS.subtitle else "video",
            confident=confident,
        )

    def _materialize_tree(self, root: Path, tree: dict) -> None:
        for name, value in tree.items():
            path = root / name
            if isinstance(value, dict):
                path.mkdir(parents=True, exist_ok=True)
                self._materialize_tree(path, value)
            elif isinstance(value, list):
                path.mkdir(parents=True, exist_ok=True)
                for filename in value:
                    (path / filename).write_text("x", encoding="utf-8")
            elif value is None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x", encoding="utf-8")
            else:
                raise TypeError(value)


class _ScopedTitleProvider:
    def __init__(self, titles):
        self.titles = titles
        self.catalog_calls: list[int | None] = []
        self.title_calls: list[tuple[int | None, tuple[int, ...]]] = []

    def tv_episode_catalog(self, *, tmdb_id: int | None):
        self.catalog_calls.append(tmdb_id)
        return TVEpisodeCatalog({99: {1: "Should Not Fetch Full Catalog"}})

    def tv_episode_titles(self, *, tmdb_id: int | None, season_numbers):
        seasons = tuple(int(item) for item in season_numbers)
        self.title_calls.append((tmdb_id, seasons))
        return {
            season: dict(self.titles.get(season, {}))
            for season in seasons
            if self.titles.get(season)
        }


if __name__ == "__main__":
    unittest.main()
