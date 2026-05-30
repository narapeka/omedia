from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.core.path import (
    display_sort_key,
    natural_sort_key,
    normalized_path_key,
    render_tag_suffix,
    safe_relative_to,
    sanitize_filename_component,
)
from app.engines.name.depot import parse_system_media_root_name, split_depot_relative_path


class PathHelperTests(unittest.TestCase):
    def test_sanitizes_filename_component(self) -> None:
        self.assertEqual(sanitize_filename_component(' A:B/C*D '), "A B C D")

    def test_protects_empty_and_reserved_names(self) -> None:
        self.assertEqual(sanitize_filename_component("..."), "Untitled")
        self.assertEqual(sanitize_filename_component("CON"), "CON_")

    def test_renders_tag_suffix_with_sanitized_text(self) -> None:
        self.assertEqual(render_tag_suffix("UHD:Remux"), "[UHD Remux]")

    def test_normalizes_path_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Folder" / "File.mkv"
            expected = str(path.resolve(strict=False)).replace("\\", "/").rstrip("/").casefold()

            self.assertEqual(normalized_path_key(path), expected)

    def test_safe_relative_to_resolved_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            child = root / "Folder" / "File.mkv"
            outside = root.parent / "Other" / "File.mkv"

            self.assertEqual(safe_relative_to(child, root), Path("Folder") / "File.mkv")
            self.assertIsNone(safe_relative_to(outside, root))

    def test_display_sort_key_uses_pinyin_and_natural_order(self) -> None:
        values = ["测试10", "阿凡达", "测试2", "[特别]"]

        self.assertEqual(sorted(values, key=display_sort_key), ["[特别]", "阿凡达", "测试2", "测试10"])

    def test_display_sort_key_uses_full_text_fallback_after_pinyin_prefix(self) -> None:
        prefix = "测" * 32

        self.assertEqual(sorted([f"{prefix}10", f"{prefix}2"], key=display_sort_key), [f"{prefix}2", f"{prefix}10"])

    def test_natural_sort_key_orders_numbers_inside_paths(self) -> None:
        values = ["Folder/10.mkv", "Folder/2.mkv"]

        self.assertEqual(sorted(values, key=natural_sort_key), ["Folder/2.mkv", "Folder/10.mkv"])

    def test_splits_tagged_system_media_root_inside_bucket(self) -> None:
        split = split_depot_relative_path("Movies/Avatar (2009) {tmdb-19995} [UHD]/Avatar (2009).mkv")

        self.assertEqual(split.organize_prefix.as_posix(), "Movies")
        self.assertEqual(split.media_root_relative_path.as_posix(), "Movies/Avatar (2009) {tmdb-19995} [UHD]")
        self.assertEqual(parse_system_media_root_name("Avatar (2009) {tmdb-19995} [UHD]")["metadata_tmdb_id"], 19995)


if __name__ == "__main__":
    unittest.main()
