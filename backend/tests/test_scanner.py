from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.domain.media import MediaType
from app.domain.origin import OriginTrigger
from app.domain.origin import OrganizePolicy, Origin
from app.domain.depot import Depot as DepotConfig, TransferPolicy
from app.domain.media import MediaExtensionPolicy
from app.domain.tv import (
    TV_STRUCTURE_DIRECT_FILES,
    TV_STRUCTURE_EMPTY,
    TV_STRUCTURE_MIXED,
    TV_STRUCTURE_SEASON_SUBFOLDERS,
)
from app.domain.depot import DepotCandidateKind, depot_candidate_id
from app.engines.scan.media import is_supported_media_file
from app.engines.scan.source import (
    detect_tv_structure,
    scan_movie_root,
    scan_origin_candidate,
    scan_origin_summary,
    scan_tv_root,
)
from app.engines.scan.depot import (
    expand_depot_candidate_files,
    scan_depot_detail_tree,
    scan_depot_summary,
)
from app.engines.scan.watch import (
    resolve_watch_candidate_path,
)
from support import TEST_MEDIA_EXTENSIONS


class ScannerTests(unittest.TestCase):
    def test_supported_extensions_include_video_subtitle_and_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            video = root / "a.mkv"
            subtitle = root / "a.srt"
            sidecar = root / "a.nfo"
            unsupported = root / "a.exe"
            for path in [video, subtitle, sidecar, unsupported]:
                path.write_text("x", encoding="utf-8")

            self.assertTrue(is_supported_media_file(video, TEST_MEDIA_EXTENSIONS))
            self.assertTrue(is_supported_media_file(subtitle, TEST_MEDIA_EXTENSIONS))
            self.assertTrue(is_supported_media_file(sidecar, TEST_MEDIA_EXTENSIONS))
            self.assertFalse(is_supported_media_file(unsupported, TEST_MEDIA_EXTENSIONS))

    def test_custom_extension_policy_controls_scanning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            custom = root / "Movie.customvideo"
            default = root / "Movie.mkv"
            custom.write_text("x", encoding="utf-8")
            default.write_text("x", encoding="utf-8")
            policy = MediaExtensionPolicy(
                video=frozenset({".customvideo"}),
                subtitle=frozenset(),
                sidecar=frozenset(),
            )

            candidates = scan_movie_root(root, extensions=policy)

            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0].files[0].path, custom)

    def test_tv_scanner_treats_immediate_subdirectories_as_show_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            show = root / "Example Show"
            show.mkdir()
            (show / "S01E01.mkv").write_text("x", encoding="utf-8")
            (root / "loose.mkv").write_text("x", encoding="utf-8")

            candidates = scan_tv_root(root, extensions=TEST_MEDIA_EXTENSIONS)

            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0].display_name, "Example Show")
            self.assertEqual(candidates[0].media_type, MediaType.TV)

    def test_tv_structure_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            direct = root / "Direct"
            direct.mkdir()
            (direct / "S01E01.mkv").write_text("x", encoding="utf-8")
            self.assertEqual(detect_tv_structure(direct, extensions=TEST_MEDIA_EXTENSIONS), TV_STRUCTURE_DIRECT_FILES)

            season = root / "Seasoned"
            (season / "Season 1").mkdir(parents=True)
            (season / "Season 1" / "S01E01.mkv").write_text("x", encoding="utf-8")
            self.assertEqual(detect_tv_structure(season, extensions=TEST_MEDIA_EXTENSIONS), TV_STRUCTURE_SEASON_SUBFOLDERS)

            mixed = root / "Mixed"
            (mixed / "Season 2").mkdir(parents=True)
            (mixed / "S01E01.mkv").write_text("x", encoding="utf-8")
            (mixed / "Season 2" / "S02E01.mkv").write_text("x", encoding="utf-8")
            self.assertEqual(detect_tv_structure(mixed, extensions=TEST_MEDIA_EXTENSIONS), TV_STRUCTURE_MIXED)

    def test_movie_scanner_discovers_folders_and_standalone_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie_folder = root / "Avatar.2009"
            movie_folder.mkdir()
            (movie_folder / "Avatar.2009.mkv").write_text("x", encoding="utf-8")
            (movie_folder / "Avatar.2009.srt").write_text("x", encoding="utf-8")
            (root / "Dune.2021.mkv").write_text("x", encoding="utf-8")
            nested_junk = root / "Junk"
            nested_junk.mkdir()
            (nested_junk / "readme.txt").write_text("x", encoding="utf-8")

            candidates = scan_movie_root(root, extensions=TEST_MEDIA_EXTENSIONS)

            self.assertEqual({candidate.structure for candidate in candidates}, {"movie_folder", "standalone_file"})
            self.assertEqual(len(candidates), 2)

    def test_watch_candidate_resolution_uses_movie_and_tv_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie_root = root / "movies"
            tv_root = root / "tv"
            movie_root.mkdir()
            tv_root.mkdir()

            standalone = movie_root / "Dune.2021.mkv"
            standalone.write_text("video", encoding="utf-8")
            movie_subtitle = movie_root / "Dune.2021.srt"
            movie_subtitle.write_text("subtitle", encoding="utf-8")
            movie_sidecar = movie_root / "Dune.2021.nfo"
            movie_sidecar.write_text("sidecar", encoding="utf-8")
            movie_folder = movie_root / "Avatar.2009"
            movie_folder.mkdir()
            (movie_folder / "Avatar.2009.mkv").write_text("video", encoding="utf-8")
            movie_unknown = movie_root / ".unknown"
            movie_unknown.mkdir()
            (movie_unknown / "Ignored.mkv").write_text("video", encoding="utf-8")

            show = tv_root / "Example Show"
            season = show / "Season 01"
            season.mkdir(parents=True)
            episode = season / "S01E01.mkv"
            episode.write_text("video", encoding="utf-8")
            tv_root_file = tv_root / "Loose.S01E01.mkv"
            tv_root_file.write_text("video", encoding="utf-8")

            movie_origin = Origin(
                id="movies",
                name="Movies",
                path=movie_root,
                media_type=MediaType.MOVIE,
                trigger=OriginTrigger.WATCH,
                policy=OrganizePolicy(target_depot_id="Depot"),
            )
            tv_origin = Origin(
                id="tv",
                name="TV",
                path=tv_root,
                media_type=MediaType.TV,
                trigger=OriginTrigger.WATCH,
                policy=OrganizePolicy(target_depot_id="Depot"),
            )

            self.assertEqual(
                resolve_watch_candidate_path(movie_origin, standalone, TEST_MEDIA_EXTENSIONS),
                standalone,
            )
            self.assertEqual(
                resolve_watch_candidate_path(movie_origin, movie_folder / "poster.jpg", TEST_MEDIA_EXTENSIONS),
                movie_folder,
            )
            self.assertIsNone(resolve_watch_candidate_path(movie_origin, movie_subtitle, TEST_MEDIA_EXTENSIONS))
            self.assertIsNone(resolve_watch_candidate_path(movie_origin, movie_sidecar, TEST_MEDIA_EXTENSIONS))
            self.assertIsNone(
                resolve_watch_candidate_path(movie_origin, movie_unknown / "Ignored.mkv", TEST_MEDIA_EXTENSIONS)
            )
            self.assertEqual(
                resolve_watch_candidate_path(tv_origin, episode, TEST_MEDIA_EXTENSIONS),
                show,
            )
            self.assertIsNone(resolve_watch_candidate_path(tv_origin, tv_root_file, TEST_MEDIA_EXTENSIONS))

            movie_candidate = scan_origin_candidate(movie_origin, movie_folder, TEST_MEDIA_EXTENSIONS)
            tv_candidate = scan_origin_candidate(tv_origin, show, TEST_MEDIA_EXTENSIONS)

            self.assertIsNotNone(movie_candidate)
            self.assertIsNotNone(tv_candidate)
            self.assertEqual(movie_candidate.structure, "movie_folder")
            self.assertEqual(tv_candidate.structure, TV_STRUCTURE_SEASON_SUBFOLDERS)
            self.assertEqual([file.relative_path.as_posix() for file in movie_candidate.files], ["Avatar.2009.mkv"])
            self.assertEqual([file.relative_path.as_posix() for file in tv_candidate.files], ["Season 01/S01E01.mkv"])

    def test_source_candidate_inventory_includes_unsupported_regular_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            movie_root = root / "movies"
            tv_root = root / "tv"
            movie_root.mkdir()
            tv_root.mkdir()
            movie_folder = movie_root / "Avatar.2009"
            movie_folder.mkdir()
            (movie_folder / "Avatar.2009.mkv").write_text("video", encoding="utf-8")
            (movie_folder / "notes.json").write_text("notes", encoding="utf-8")
            tv_show = tv_root / "Show"
            tv_show.mkdir()
            (tv_show / "S01E01.mkv").write_text("video", encoding="utf-8")
            (tv_show / "debug.log").write_text("log", encoding="utf-8")

            movie_candidate = scan_movie_root(movie_root, extensions=TEST_MEDIA_EXTENSIONS)[0]
            tv_candidate = scan_tv_root(tv_root, extensions=TEST_MEDIA_EXTENSIONS)[0]

            self.assertIn("notes.json", {file.relative_path.as_posix() for file in movie_candidate.files})
            self.assertIn("debug.log", {file.relative_path.as_posix() for file in tv_candidate.files})

    def test_tv_and_movie_scanners_ignore_generic_sidecar_only_folders(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tv_sidecar = root / "TV.Sidecars"
            movie_sidecar = root / "Movie.Sidecars"
            tv_subtitle = root / "TV.Subtitle"
            movie_subtitle = root / "Movie.Subtitle"
            for folder in [tv_sidecar, movie_sidecar, tv_subtitle, movie_subtitle]:
                folder.mkdir()
            for name in ["show.nfo", "poster.jpg"]:
                (tv_sidecar / name).write_text("x", encoding="utf-8")
                (movie_sidecar / name).write_text("x", encoding="utf-8")
            (tv_subtitle / "S01E01.srt").write_text("x", encoding="utf-8")
            (movie_subtitle / "Movie.Subtitle.srt").write_text("x", encoding="utf-8")

            tv_candidates = scan_tv_root(root, extensions=TEST_MEDIA_EXTENSIONS)
            movie_candidates = scan_movie_root(root, extensions=TEST_MEDIA_EXTENSIONS)

            self.assertNotIn("TV.Subtitle", {candidate.display_name for candidate in tv_candidates})
            self.assertNotIn("TV.Sidecars", {candidate.display_name for candidate in tv_candidates})
            self.assertNotIn("Movie.Subtitle", {candidate.display_name for candidate in movie_candidates})
            self.assertNotIn("Movie.Sidecars", {candidate.display_name for candidate in movie_candidates})

    def test_tv_structure_detection_ignores_generic_sidecar_only_subfolders(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            show = root / "Show"
            (show / "Extras").mkdir(parents=True)
            (show / "Extras" / "poster.jpg").write_text("x", encoding="utf-8")
            (show / "S01E01.srt").write_text("x", encoding="utf-8")

            self.assertEqual(detect_tv_structure(show, extensions=TEST_MEDIA_EXTENSIONS), TV_STRUCTURE_EMPTY)

    def test_small_non_subtitle_threshold_filters_movie_candidates_and_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            small_standalone = root / "Sample.mkv"
            eligible_standalone = root / "Feature.mkv"
            small_standalone.write_bytes(b"x" * 9)
            eligible_standalone.write_bytes(b"x" * 10)

            folder = root / "Movie"
            folder.mkdir()
            (folder / "Movie.mkv").write_bytes(b"x" * 20)
            (folder / "sample.mkv").write_bytes(b"x")
            (folder / "Movie.srt").write_bytes(b"x")
            (folder / "notes.txt").write_bytes(b"x")

            candidates = scan_movie_root(
                root,
                extensions=TEST_MEDIA_EXTENSIONS,
                min_non_subtitle_file_size_bytes=10,
            )
            by_name = {candidate.display_name: candidate for candidate in candidates}

            self.assertEqual(set(by_name), {"Feature", "Movie"})
            self.assertEqual([file.relative_path.as_posix() for file in by_name["Feature"].files], ["Feature.mkv"])
            self.assertEqual(
                {file.relative_path.as_posix() for file in by_name["Movie"].files},
                {"Movie.mkv", "Movie.srt"},
            )

    def test_small_non_subtitle_threshold_filters_tv_candidates_and_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            small_only = root / "Small Only"
            small_only.mkdir()
            (small_only / "S01E01.mkv").write_bytes(b"x")
            (small_only / "S01E01.srt").write_bytes(b"x")

            show = root / "Show"
            season = show / "Season 01"
            season.mkdir(parents=True)
            (show / "sample.mkv").write_bytes(b"x")
            (show / "sample.srt").write_bytes(b"x")
            (season / "S01E01.mkv").write_bytes(b"x" * 20)
            (season / "ad.mkv").write_bytes(b"x")
            (season / "notes.txt").write_bytes(b"x")

            candidates = scan_tv_root(
                root,
                extensions=TEST_MEDIA_EXTENSIONS,
                min_non_subtitle_file_size_bytes=10,
            )
            by_name = {candidate.display_name: candidate for candidate in candidates}

            self.assertEqual(set(by_name), {"Show"})
            self.assertEqual(by_name["Show"].structure, TV_STRUCTURE_SEASON_SUBFOLDERS)
            self.assertEqual(
                {file.relative_path.as_posix() for file in by_name["Show"].files},
                {"sample.srt", "Season 01/S01E01.mkv"},
            )

    def test_origin_scan_excludes_reserved_unknown_from_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            unknown = root / ".unknown"
            unknown.mkdir()
            (unknown / "Unknown.mkv").write_text("x", encoding="utf-8")
            origin = Origin(
                id="origin",
                name="Origin",
                path=root,
                media_type=MediaType.MOVIE,
                trigger=OriginTrigger.WATCH,
                policy=OrganizePolicy(target_depot_id="Depot"),
            )

            scan = scan_origin_summary(origin, TEST_MEDIA_EXTENSIONS)

            self.assertEqual(scan.candidate_count, 0)
            self.assertEqual(scan.file_count, 0)
            self.assertEqual(scan.unknown_count, 1)

    def test_empty_and_unsupported_roots_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            show = root / "Show"
            show.mkdir()
            (show / "file.exe").write_text("x", encoding="utf-8")

            self.assertEqual(scan_tv_root(root, extensions=TEST_MEDIA_EXTENSIONS), [])
            self.assertEqual(scan_movie_root(root, extensions=TEST_MEDIA_EXTENSIONS), [])

    def test_fingerprint_is_stable_for_same_candidate_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            show = root / "Show"
            show.mkdir()
            path = show / "S01E01.mkv"
            path.write_text("x", encoding="utf-8")

            first = scan_tv_root(root, extensions=TEST_MEDIA_EXTENSIONS)[0].fingerprint
            second = scan_tv_root(root, extensions=TEST_MEDIA_EXTENSIONS)[0].fingerprint

            self.assertEqual(first, second)

    def test_depot_scan_exposes_physical_folder_and_loose_file_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            Depot = DepotConfig(
                id="Depot",
                name="Movie Depot",
                path=root / "Depot",
                media_type=MediaType.MOVIE,
                policy=TransferPolicy(target_library_path=root / "library"),
            )
            movie = Depot.path / "Avatar (2009) {tmdb-19995}"
            nested = movie / "extras"
            nested.mkdir(parents=True)
            (movie / "Avatar (2009).mkv").write_text("video", encoding="utf-8")
            (movie / "Avatar (2009).srt").write_text("subtitle", encoding="utf-8")
            (nested / "poster.jpg").write_text("poster", encoding="utf-8")
            (Depot.path / "Loose.mkv").write_text("loose", encoding="utf-8")

            detail = scan_depot_detail_tree(Depot, TEST_MEDIA_EXTENSIONS)
            summary = scan_depot_summary(Depot, TEST_MEDIA_EXTENSIONS)

            by_name = {candidate.display_name: candidate for candidate in detail.candidates}
            self.assertEqual(set(by_name), {"Avatar (2009) {tmdb-19995}", "Loose.mkv"})
            self.assertEqual(by_name["Loose.mkv"].kind.value, "file")
            self.assertEqual(by_name["Avatar (2009) {tmdb-19995}"].kind.value, "folder")
            self.assertEqual(
                {file.candidate_relative_path.as_posix() for file in by_name["Avatar (2009) {tmdb-19995}"].files},
                {"Avatar (2009).mkv", "Avatar (2009).srt", "extras/poster.jpg"},
            )
            self.assertEqual(by_name["Avatar (2009) {tmdb-19995}"].file_count, 3)
            self.assertEqual(by_name["Avatar (2009) {tmdb-19995}"].media_count, 2)
            self.assertEqual(summary.pending_count, 4)

    def test_depot_scan_keeps_empty_folder_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            Depot = DepotConfig(
                id="Depot",
                name="Movie Depot",
                path=root / "Depot",
                media_type=MediaType.MOVIE,
                policy=TransferPolicy(target_library_path=root / "library"),
            )
            (Depot.path / "Empty").mkdir(parents=True)

            detail = scan_depot_detail_tree(Depot, TEST_MEDIA_EXTENSIONS)

            self.assertEqual(len(detail.candidates), 1)
            self.assertEqual(detail.candidates[0].display_name, "Empty")
            self.assertEqual(detail.candidates[0].file_count, 0)

    def test_depot_scan_keeps_empty_root_folder_candidate_for_nested_empty_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            Depot = DepotConfig(
                id="Depot",
                name="Movie Depot",
                path=root / "Depot",
                media_type=MediaType.MOVIE,
                policy=TransferPolicy(target_library_path=root / "library"),
            )
            (Depot.path / "Loose Prefix" / "Nested Empty").mkdir(parents=True)

            detail = scan_depot_detail_tree(Depot, TEST_MEDIA_EXTENSIONS)

            self.assertEqual(len(detail.candidates), 1)
            self.assertEqual(detail.candidates[0].relative_path, Path("Loose Prefix"))
            self.assertEqual(detail.candidates[0].display_name, "Loose Prefix")
            self.assertEqual(detail.candidates[0].file_count, 0)

    def test_depot_scan_does_not_traverse_directory_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outside = root / "outside"
            outside.mkdir()
            (outside / "outside.mkv").write_text("outside", encoding="utf-8")
            Depot = DepotConfig(
                id="Depot",
                name="Movie Depot",
                path=root / "Depot",
                media_type=MediaType.MOVIE,
                policy=TransferPolicy(target_library_path=root / "library"),
            )
            candidate = Depot.path / "Candidate"
            candidate.mkdir(parents=True)
            (candidate / "inside.mkv").write_text("inside", encoding="utf-8")
            try:
                (candidate / "outside-link").symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlink unavailable: {exc}")

            detail = scan_depot_detail_tree(Depot, TEST_MEDIA_EXTENSIONS)

            scanned = detail.candidates[0]
            self.assertEqual({file.candidate_relative_path.as_posix() for file in scanned.files}, {"inside.mkv"})
            self.assertEqual(scanned.blocked_reason, "contains_link_or_reparse_point")
            self.assertEqual(
                {file.relative_path.as_posix() for file in expand_depot_candidate_files(detail.candidates)},
                {"Candidate/inside.mkv"},
            )

    def test_depot_scan_groups_media_boundary_candidates_under_organize_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            Depot = DepotConfig(
                id="Depot",
                name="Movie Depot",
                path=root / "Depot",
                media_type=MediaType.MOVIE,
                policy=TransferPolicy(target_library_path=root / "library"),
            )
            inception = Depot.path / "欧美电影" / "科幻" / "Inception (2010) {tmdb-27205}"
            avatar = Depot.path / "欧美电影" / "科幻" / "Avatar (2009) {tmdb-19995}"
            inception.mkdir(parents=True)
            avatar.mkdir(parents=True)
            (inception / "Inception.mkv").write_text("video", encoding="utf-8")
            (avatar / "Avatar.mkv").write_text("video", encoding="utf-8")

            detail = scan_depot_detail_tree(Depot, TEST_MEDIA_EXTENSIONS)

            self.assertEqual({candidate.display_name for candidate in detail.candidates}, {"Inception (2010) {tmdb-27205}", "Avatar (2009) {tmdb-19995}"})
            self.assertEqual({candidate.group.organize_prefix.as_posix() for candidate in detail.candidates if candidate.group}, {"欧美电影/科幻"})
            self.assertEqual({candidate.media_relative_path.as_posix() for candidate in detail.candidates if candidate.media_relative_path}, {"Inception (2010) {tmdb-27205}", "Avatar (2009) {tmdb-19995}"})
            self.assertNotIn("欧美电影", {candidate.display_name for candidate in detail.candidates})

    def test_depot_scan_leaves_root_media_candidates_ungrouped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            Depot = DepotConfig(
                id="Depot",
                name="Movie Depot",
                path=root / "Depot",
                media_type=MediaType.MOVIE,
                policy=TransferPolicy(target_library_path=root / "library"),
            )
            movie = Depot.path / "Inception (2010) {tmdb-27205}"
            movie.mkdir(parents=True)
            (movie / "Inception.mkv").write_text("video", encoding="utf-8")

            detail = scan_depot_detail_tree(Depot, TEST_MEDIA_EXTENSIONS)

            self.assertEqual(len(detail.candidates), 1)
            self.assertIsNone(detail.candidates[0].group)
            self.assertEqual(detail.candidates[0].media_relative_path, Path("Inception (2010) {tmdb-27205}"))

    def test_depot_candidate_ids_change_when_path_case_changes(self) -> None:
        upper = depot_candidate_id("Depot", DepotCandidateKind.FOLDER, Path("Movie"))
        lower = depot_candidate_id("Depot", DepotCandidateKind.FOLDER, Path("movie"))

        self.assertNotEqual(upper, lower)


if __name__ == "__main__":
    unittest.main()
