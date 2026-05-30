from __future__ import annotations

import unittest
from pathlib import Path

from app.engines.plan.subtitle.selection import SubtitleCandidate, chinese_marker_rank, select_subtitle_candidates


class SubtitleSelectionTests(unittest.TestCase):
    def test_ordered_marker_priority_beats_stable_ordering(self) -> None:
        selected = select_subtitle_candidates(
            [
                self._candidate("Show.S01E01.zh.srt"),
                self._candidate("Show.S01E01.chs.eng.srt"),
            ]
        )[0]

        self.assertEqual(selected.selected.source_path.name, "Show.S01E01.chs.eng.srt")
        self.assertEqual(selected.ignored[0].source_path.name, "Show.S01E01.zh.srt")

    def test_wildcard_gap_marker_matches_compact_and_separated_forms(self) -> None:
        self.assertEqual(chinese_marker_rank(Path("Show.S01E01.chseng.srt")), 0)
        self.assertEqual(chinese_marker_rank(Path("Show.S01E01.chs-eng.srt")), 0)
        self.assertEqual(chinese_marker_rank(Path("Show.S01E01.zh.en.srt")), 1)
        self.assertEqual(chinese_marker_rank(Path("Show.S01E01(简体英文).sup")), 2)

    def test_different_extensions_are_preserved(self) -> None:
        selections = select_subtitle_candidates(
            [
                self._candidate("Show.S01E01.zh.srt"),
                self._candidate("Show.S01E01.zh.sup"),
            ]
        )

        self.assertEqual({selection.selected.extension for selection in selections}, {".srt", ".sup"})

    def test_no_marker_uses_stable_source_ordering(self) -> None:
        selected = select_subtitle_candidates(
            [
                self._candidate("Show.S01E01.b.srt"),
                self._candidate("Show.S01E01.a.srt"),
            ]
        )[0]

        self.assertEqual(selected.selected.source_path.name, "Show.S01E01.a.srt")

    def _candidate(self, relative_path: str) -> SubtitleCandidate:
        path = Path(relative_path)
        return SubtitleCandidate(
            value=relative_path,
            group_key="show-s01e01",
            source_path=path,
            relative_path=path,
            extension=path.suffix.lower(),
        )


if __name__ == "__main__":
    unittest.main()
