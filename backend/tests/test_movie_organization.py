from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path

from app.domain.match import ConfidenceLevel, HintSource, MatchHint, MatchResult, TMDBCandidate, TitleHint, TitleKind
from app.domain.media import MediaExtensionPolicy, MediaType
from app.domain.origin import OrganizePolicy
from app.engines.name.renderer import MovieNamingInput, render_movie_path
from app.engines.name.movie.part import extract_movie_part_token
from app.engines.name.movie.source import (
    build_movie_identity,
    extract_movie_source_name,
)
from app.engines.plan.movie.planner import collect_movie_file_set
from app.services.identify.match import MatchService
from app.services.identify.preview import Preview
from app.engines.scan.source import scan_movie_root
from support import FakeTMDB, FixedLLMHintExtractor, FixedMediaNameExtractor, TEST_MEDIA_EXTENSIONS


class MovieOrganizationTests(unittest.TestCase):
    def test_movie_package_does_not_export_implementation(self) -> None:
        movie = importlib.import_module("app.engines.plan.movie")
        movie_name = importlib.import_module("app.engines.name.movie")

        self.assertFalse(hasattr(movie, "__all__"))
        self.assertNotIn("extract_movie_source_name", vars(movie))
        self.assertNotIn("collect_movie_file_set", vars(movie))
        self.assertNotIn("extract_movie_part_token", vars(movie))
        self.assertFalse(hasattr(movie_name, "__all__"))
        self.assertNotIn("extract_movie_source_name", vars(movie_name))
        self.assertNotIn("extract_movie_part_token", vars(movie_name))

    def test_source_name_extraction_from_file_and_folder(self) -> None:
        title, year, tag = extract_movie_source_name(Path("Avatar.2009.#UHD#.mkv"), extensions=TEST_MEDIA_EXTENSIONS)
        folder_title, folder_year, _ = extract_movie_source_name(Path("Avatar.2009"), extensions=TEST_MEDIA_EXTENSIONS)

        self.assertEqual(title, "Avatar")
        self.assertEqual(year, 2009)
        self.assertEqual(tag.raw_tag, "UHD")
        self.assertEqual(folder_title, "Avatar")
        self.assertEqual(folder_year, 2009)

    def test_movie_matching_uses_movie_media_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie = root / "Avatar.2009.mkv"
            movie.write_text("x", encoding="utf-8")
            candidate = scan_movie_root(root, extensions=TEST_MEDIA_EXTENSIONS)[0]
            tmdb = FakeTMDB()
            tmdb.search_results = [TMDBCandidate(1, MediaType.MOVIE, "Avatar", year=2009)]
            matcher = MatchService(
                tmdb,
                media_name_extractor=FixedMediaNameExtractor(
                    MatchHint(
                        titles=(TitleHint("Avatar", TitleKind.ENGLISH, HintSource.LLM),),
                        year=2009,
                    )
                ),
                llm_extractor=FixedLLMHintExtractor(MatchHint()),
            )

            result = matcher.match(candidate)

            self.assertEqual(result.media_type, MediaType.MOVIE)
            self.assertEqual(result.confidence, ConfidenceLevel.HIGH)

    def test_emby_movie_destination_and_tag(self) -> None:
        movie = build_movie_identity(Path("Avatar.2009.#UHD#.mkv"), tmdb_id=19995, extensions=TEST_MEDIA_EXTENSIONS)
        rendered = render_movie_path(
            MovieNamingInput(
                title=movie.title or movie.source_name,
                year=movie.year,
                tmdb_id=movie.tmdb_id,
                extension=".mkv",
                tag_suffix=movie.tag.rendered_suffix if movie.tag else None,
            )
        )

        self.assertEqual(rendered.relative_path, Path("Avatar (2009) {tmdb-19995} [UHD]/Avatar (2009).mkv"))
        self.assertEqual(Path("Depot") / rendered.relative_path, Path("Depot/Avatar (2009) {tmdb-19995} [UHD]/Avatar (2009).mkv"))

    def test_movie_subtitle_and_sidecar_planning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Avatar.2009"
            folder.mkdir()
            for name in ["Avatar.2009.mkv", "Avatar.2009.srt", "movie.nfo"]:
                (folder / name).write_text("x", encoding="utf-8")
            candidate = scan_movie_root(root, extensions=TEST_MEDIA_EXTENSIONS)[0]

            file_set = collect_movie_file_set(candidate, extensions=TEST_MEDIA_EXTENSIONS)

            self.assertIsNotNone(file_set)
            assert file_set is not None
            self.assertEqual(file_set.primary_file.name, "Avatar.2009.mkv")
            self.assertEqual(file_set.subtitle_files[0].name, "Avatar.2009.srt")
            self.assertEqual(file_set.sidecar_files[0].name, "movie.nfo")

    def test_movie_preview_includes_selected_subtitles_and_excludes_generic_sidecars(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Avatar.2009"
            folder.mkdir()
            for name in [
                "Avatar.2009.mkv",
                "Avatar.2009.srt",
                "Avatar.2009.zh.srt",
                "Avatar.2009.sup",
                "Avatar.2009.nfo",
                "poster.jpg",
            ]:
                (folder / name).write_text("x", encoding="utf-8")
            candidate = scan_movie_root(root, extensions=TEST_MEDIA_EXTENSIONS)[0]

            previews = Preview.for_candidate(
                media_candidate=candidate,
                source_root=root,
                match_result=self._match_result(candidate.id),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )

            by_source = {item.source_path.name: item for item in previews}
            self.assertEqual(set(by_source), {"Avatar.2009.mkv", "Avatar.2009.zh.srt", "Avatar.2009.sup"})
            self.assertEqual(
                by_source["Avatar.2009.zh.srt"].preview.proposed_relative_path,
                Path("Avatar (2009) {tmdb-19995}/Avatar (2009).srt"),
            )
            self.assertEqual(
                by_source["Avatar.2009.sup"].preview.proposed_relative_path,
                Path("Avatar (2009) {tmdb-19995}/Avatar (2009).sup"),
            )
            self.assertEqual(by_source["Avatar.2009.zh.srt"].evidence["movie_plan"]["media_kind"], "subtitle")
            self.assertEqual(
                by_source["Avatar.2009.zh.srt"].evidence["movie_plan"]["ignored_duplicate_subtitles"],
                ["Avatar.2009.srt"],
            )

    def test_movie_subtitle_duplicate_fallback_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Avatar.2009"
            folder.mkdir()
            for name in ["Avatar.2009.mkv", "Avatar.2009.b.srt", "Avatar.2009.a.srt"]:
                (folder / name).write_text("x", encoding="utf-8")
            candidate = scan_movie_root(root, extensions=TEST_MEDIA_EXTENSIONS)[0]

            previews = Preview.for_candidate(
                media_candidate=candidate,
                source_root=root,
                match_result=self._match_result(candidate.id),
                policy=OrganizePolicy(target_depot_id="Depot"),
                extensions=TEST_MEDIA_EXTENSIONS,
            )

            self.assertEqual(
                {item.source_path.name for item in previews},
                {"Avatar.2009.mkv", "Avatar.2009.a.srt"},
            )

    def test_movie_multi_video_folder_plans_complete_unique_part_tokens(self) -> None:
        cases = [
            (["Avatar.2009.CD1.mkv", "Avatar.2009.CD2.mkv"], ["CD1", "CD2"]),
            (["Avatar.2009.DISC1.mkv", "Avatar.2009.DISC2.mkv"], ["DISC1", "DISC2"]),
            (["Avatar.2009.D01.mkv", "Avatar.2009.D02.mkv"], ["D01", "D02"]),
        ]
        for names, tokens in cases:
            with self.subTest(names=names):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    folder = root / "Avatar.2009"
                    folder.mkdir()
                    for name in names:
                        (folder / name).write_text("x", encoding="utf-8")
                    candidate = scan_movie_root(root, extensions=TEST_MEDIA_EXTENSIONS)[0]

                    previews = self._previews(candidate, root, TEST_MEDIA_EXTENSIONS)

                    primary_previews = self._primary_previews(previews)
                    self.assertEqual({item.source_path.name for item in primary_previews}, set(names))
                    self.assertEqual(
                        {item.evidence["movie_plan"]["part_token"] for item in primary_previews},
                        set(tokens),
                    )
                    self.assertEqual(
                        {item.preview.proposed_relative_path for item in primary_previews},
                        {
                            Path(f"Avatar (2009) {{tmdb-19995}}/Avatar (2009) - {token}.mkv")
                            for token in tokens
                        },
                    )

    def test_movie_multi_video_folder_plans_variant_tokens_and_iso_videos(self) -> None:
        extensions = MediaExtensionPolicy(
            video=TEST_MEDIA_EXTENSIONS.video | frozenset({".iso"}),
            subtitle=TEST_MEDIA_EXTENSIONS.subtitle,
            sidecar=TEST_MEDIA_EXTENSIONS.sidecar,
        )
        token_names = {
            "Theatrical": "Avatar.2009.Theatrical.iso",
            "Extended": "Avatar.2009.Extended.iso",
            "剧场版": "Avatar.2009.剧场版.iso",
            "加长版": "Avatar.2009.加长版.iso",
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Avatar.2009"
            folder.mkdir()
            for name in token_names.values():
                (folder / name).write_text("x", encoding="utf-8")
            candidate = scan_movie_root(root, extensions=extensions)[0]

            previews = self._previews(candidate, root, extensions)

            primary_previews = self._primary_previews(previews)
            self.assertEqual({item.source_path.name for item in primary_previews}, set(token_names.values()))
            self.assertEqual(
                {item.evidence["movie_plan"]["part_token"] for item in primary_previews},
                set(token_names),
            )
            self.assertEqual(
                {item.preview.proposed_relative_path for item in primary_previews},
                {
                    Path(f"Avatar (2009) {{tmdb-19995}}/Avatar (2009) - {token}.iso")
                    for token in token_names
                },
            )

    def test_movie_part_tokens_are_ignored_for_single_video_and_standalone_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Avatar.2009"
            folder.mkdir()
            (folder / "Avatar.2009.CD1.mkv").write_text("video", encoding="utf-8")
            (folder / "Avatar.2009.CD1.srt").write_text("subtitle", encoding="utf-8")
            standalone = root / "Avatar.2009.Theatrical.mp4"
            standalone.write_text("video", encoding="utf-8")
            candidates = scan_movie_root(root, extensions=TEST_MEDIA_EXTENSIONS)
            by_structure = {candidate.structure: candidate for candidate in candidates}

            folder_previews = self._previews(by_structure["movie_folder"], root, TEST_MEDIA_EXTENSIONS)
            standalone_previews = self._previews(by_structure["standalone_file"], root, TEST_MEDIA_EXTENSIONS)

            folder_primary = self._primary_previews(folder_previews)[0]
            standalone_primary = self._primary_previews(standalone_previews)[0]
            self.assertEqual(
                folder_primary.preview.proposed_relative_path,
                Path("Avatar (2009) {tmdb-19995}/Avatar (2009).mkv"),
            )
            self.assertNotIn("part_token", folder_primary.evidence["movie_plan"])
            self.assertEqual(
                standalone_primary.preview.proposed_relative_path,
                Path("Avatar (2009) {tmdb-19995}/Avatar (2009).mp4"),
            )
            self.assertNotIn("part_token", standalone_primary.evidence["movie_plan"])
            self.assertEqual(
                {item.source_path.name for item in folder_previews},
                {"Avatar.2009.CD1.mkv", "Avatar.2009.CD1.srt"},
            )

    def test_movie_multi_video_folder_falls_back_for_missing_or_duplicate_tokens(self) -> None:
        cases = [
            ["Avatar.2009.CD1.mkv", "Avatar.2009.NoToken.mkv"],
            ["Avatar.2009.CD1.mkv", "Avatar.2009.cd1.mp4"],
        ]
        for names in cases:
            with self.subTest(names=names):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    folder = root / "Avatar.2009"
                    folder.mkdir()
                    for name in names:
                        (folder / name).write_text("x", encoding="utf-8")
                    candidate = scan_movie_root(root, extensions=TEST_MEDIA_EXTENSIONS)[0]

                    previews = self._previews(candidate, root, TEST_MEDIA_EXTENSIONS)

                    primary_previews = self._primary_previews(previews)
                    self.assertEqual([item.source_path.name for item in primary_previews], ["Avatar.2009.CD1.mkv"])
                    self.assertEqual(
                        primary_previews[0].preview.proposed_relative_path,
                        Path("Avatar (2009) {tmdb-19995}/Avatar (2009).mkv"),
                    )
                    self.assertNotIn("part_token", primary_previews[0].evidence["movie_plan"])

    def test_movie_part_token_rendering_sanitizes_suffix(self) -> None:
        tokenless = render_movie_path(
            MovieNamingInput(title="Avatar", year=2009, tmdb_id=19995, extension=".mkv")
        )
        tokenized = render_movie_path(
            MovieNamingInput(title="Avatar", year=2009, tmdb_id=19995, extension=".mkv", part_token="Cut:One")
        )

        self.assertEqual(
            tokenless.relative_path,
            Path("Avatar (2009) {tmdb-19995}/Avatar (2009).mkv"),
        )
        self.assertEqual(
            tokenized.relative_path,
            Path("Avatar (2009) {tmdb-19995}/Avatar (2009) - Cut_One.mkv"),
        )
        self.assertIn("movie_part_token_sanitized", tokenized.warnings)

    def _previews(self, candidate, root: Path, extensions: MediaExtensionPolicy):
        return Preview.for_candidate(
            media_candidate=candidate,
            source_root=root,
            match_result=self._match_result(candidate.id),
            policy=OrganizePolicy(target_depot_id="Depot"),
            extensions=extensions,
        )

    def _primary_previews(self, previews):
        return [
            item
            for item in previews
            if item.evidence["movie_plan"]["media_kind"] == "primary"
        ]

    def _match_result(self, candidate_id: str) -> MatchResult:
        return MatchResult(
            candidate_id=candidate_id,
            media_type=MediaType.MOVIE,
            confidence=ConfidenceLevel.HIGH,
            title="Avatar",
            year=2009,
            tmdb_id=19995,
            metadata={"title": "Avatar", "release_year": 2009, "tmdb_id": 19995},
        )


if __name__ == "__main__":
    unittest.main()
