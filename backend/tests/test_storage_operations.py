from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.infra.fs.cleanup import cleanup_source_parents
from app.infra.fs.move import classify_timeout_result
from app.infra.fs.move import move_with_replace
from app.infra.fs.rename import StorageRenameStatus, rename_verified_file, rename_verified_tree
from app.infra.fs.result import StorageMoveStatus


class StorageCleanupTests(unittest.TestCase):
    def test_cleanup_prunes_empty_parents_until_protected_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            season = root / "Show" / "Season 1"
            season.mkdir(parents=True)

            result = cleanup_source_parents(season, root, {".nfo"})

            self.assertTrue(result.attempted)
            self.assertFalse(season.exists())
            self.assertFalse((root / "Show").exists())
            self.assertTrue(root.exists())
            self.assertEqual(result.stop_reason, "protected_root")

    def test_cleanup_deletes_sidecar_and_junk_only_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            season = root / "Show" / "Season 1"
            season.mkdir(parents=True)
            (season / "episode.nfo").write_text("metadata", encoding="utf-8")
            (season / ".DS_Store").write_text("junk", encoding="utf-8")

            result = cleanup_source_parents(season, root, {".nfo"})

            self.assertFalse(season.exists())
            self.assertFalse((root / "Show").exists())
            self.assertIn("Show/Season 1/episode.nfo", result.removed_files)
            self.assertIn("Show/Season 1/.DS_Store", result.removed_files)

    def test_cleanup_deletes_tree_with_only_empty_subdirectories(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            season = root / "Show" / "Season 1"
            (season / "Extras").mkdir(parents=True)

            result = cleanup_source_parents(season, root, {".nfo"})

            self.assertFalse(season.exists())
            self.assertFalse((root / "Show").exists())
            self.assertEqual(result.stop_reason, "protected_root")

    def test_cleanup_preserves_non_sidecar_leftovers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            season = root / "Show" / "Season 1"
            season.mkdir(parents=True)
            (season / "episode.nfo").write_text("metadata", encoding="utf-8")
            (season / "notes.json").write_text("keep", encoding="utf-8")

            result = cleanup_source_parents(season, root, {".nfo"})

            self.assertTrue(season.exists())
            self.assertTrue((season / "notes.json").exists())
            self.assertEqual(result.stopped_at, "Show/Season 1")
            self.assertEqual(result.stop_reason, "contains_non_sidecar")

    def test_cleanup_refuses_outside_protected_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outside = root.parent / f"{root.name}-outside"
            outside.mkdir()
            try:
                result = cleanup_source_parents(outside, root, {".nfo"})

                self.assertFalse(result.attempted)
                self.assertEqual(result.stop_reason, "outside_protected_root")
                self.assertTrue(outside.exists())
            finally:
                outside.rmdir()

    def test_cleanup_preserves_symlink_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            season = root / "Show" / "Season 1"
            target = root / "target"
            season.mkdir(parents=True)
            target.mkdir()
            link = season / "linked"
            try:
                os.symlink(target, link, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink unavailable: {exc}")

            result = cleanup_source_parents(season, root, {".nfo"})

            self.assertTrue(season.exists())
            self.assertTrue(link.exists())
            self.assertEqual(result.stop_reason, "contains_link_or_reparse_point")


class StorageMoveTests(unittest.TestCase):
    def test_move_with_replace_replaces_destination_without_copy_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.mkv"
            destination = root / "dest" / "source.mkv"
            source.write_text("new", encoding="utf-8")
            destination.parent.mkdir()
            destination.write_text("old", encoding="utf-8")

            result = move_with_replace(source, destination, cleanup_root=root, sidecar_extensions={".nfo"})

            self.assertEqual(result.status, StorageMoveStatus.SUCCEEDED)
            self.assertFalse(source.exists())
            self.assertEqual(destination.read_text(encoding="utf-8"), "new")
            self.assertEqual(result.cleanup.stop_reason, "protected_root")

    def test_move_with_replace_reports_direct_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "missing.mkv"
            destination = root / "dest.mkv"

            result = move_with_replace(source, destination, cleanup_root=root, sidecar_extensions={".nfo"})

            self.assertEqual(result.status, StorageMoveStatus.FAILED)
            self.assertEqual(result.error_type, "FileNotFoundError")
            self.assertFalse(destination.exists())

    def test_timeout_classification_source_remaining(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.mkv"
            destination = root / "dest.mkv"
            source.write_text("x", encoding="utf-8")

            result = classify_timeout_result(source, destination)

            self.assertEqual(result.status, StorageMoveStatus.TIMEOUT)
            self.assertTrue(result.retryable_timeout)

    def test_timeout_classification_completed_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.mkv"
            destination = root / "dest.mkv"
            destination.write_text("x", encoding="utf-8")

            result = classify_timeout_result(source, destination)

            self.assertEqual(result.status, StorageMoveStatus.SUCCEEDED)
            self.assertTrue(result.timed_out)

    def test_timeout_classification_ambiguous_states(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.mkv"
            destination = root / "dest.mkv"
            source.write_text("x", encoding="utf-8")
            destination.write_text("x", encoding="utf-8")

            both_present = classify_timeout_result(source, destination)

            source.unlink()
            destination.unlink()
            both_missing = classify_timeout_result(source, destination)

            self.assertEqual(both_present.status, StorageMoveStatus.AMBIGUOUS)
            self.assertEqual(both_missing.status, StorageMoveStatus.AMBIGUOUS)


class StorageRenameTests(unittest.TestCase):
    def test_rename_verified_file_renames_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "Avatar.mkv"
            source.write_text("movie", encoding="utf-8")

            result = rename_verified_file(source, "Avatar.2009.mkv", protected_root=root)

            self.assertEqual(result.status, StorageRenameStatus.SUCCEEDED)
            self.assertFalse(source.exists())
            self.assertTrue((root / "Avatar.2009.mkv").exists())
            self.assertEqual(result.file_count, 1)
            self.assertEqual(result.total_size, len("movie"))

    def test_rename_verified_tree_renames_folder_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Avatar"
            folder.mkdir()
            (folder / "Avatar.mkv").write_text("movie", encoding="utf-8")

            result = rename_verified_tree(folder, "Avatar.2009", protected_root=root)

            self.assertEqual(result.status, StorageRenameStatus.SUCCEEDED)
            self.assertFalse(folder.exists())
            self.assertTrue((root / "Avatar.2009" / "Avatar.mkv").exists())
            self.assertEqual(result.file_count, 1)

    def test_rename_verified_file_reports_missing_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            result = rename_verified_file(root / "missing.mkv", "new.mkv", protected_root=root)

            self.assertEqual(result.status, StorageRenameStatus.MISSING)
            self.assertFalse((root / "new.mkv").exists())

    def test_rename_verified_file_reports_target_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.mkv"
            target = root / "target.mkv"
            source.write_text("source", encoding="utf-8")
            target.write_text("target", encoding="utf-8")

            result = rename_verified_file(source, "target.mkv", protected_root=root)

            self.assertEqual(result.status, StorageRenameStatus.CONFLICT)
            self.assertTrue(source.exists())
            self.assertEqual(target.read_text(encoding="utf-8"), "target")

    def test_rename_verified_file_rejects_path_separator(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.mkv"
            source.write_text("source", encoding="utf-8")

            result = rename_verified_file(source, "nested/source.mkv", protected_root=root)

            self.assertEqual(result.status, StorageRenameStatus.BLOCKED)
            self.assertEqual(result.blocked_reason, "path_separator")
            self.assertTrue(source.exists())

    def test_rename_verified_file_rejects_outside_root_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outside = root.parent / f"{root.name}-outside-rename.mkv"
            outside.write_text("outside", encoding="utf-8")
            try:
                result = rename_verified_file(outside, "new.mkv", protected_root=root)

                self.assertEqual(result.status, StorageRenameStatus.BLOCKED)
                self.assertEqual(result.blocked_reason, "outside_protected_root")
                self.assertTrue(outside.exists())
            finally:
                outside.unlink(missing_ok=True)

    def test_rename_verified_tree_blocks_symlink_or_reparse(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "Avatar"
            target = root / "target"
            folder.mkdir()
            target.mkdir()
            (folder / "Avatar.mkv").write_text("movie", encoding="utf-8")
            try:
                os.symlink(target, folder / "linked", target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink unavailable: {exc}")

            result = rename_verified_tree(folder, "Avatar.2009", protected_root=root)

            self.assertEqual(result.status, StorageRenameStatus.BLOCKED)
            self.assertEqual(result.blocked_reason, "contains_link_or_reparse_point")
            self.assertTrue(folder.exists())


if __name__ == "__main__":
    unittest.main()
