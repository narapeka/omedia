from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from app.domain.media import MediaType
from app.domain.organize import SourceActionOperation, SourceActionStatus
from app.services.organize.source import (
    SourceActionOutcome,
    source_action_activity,
)


class SourceOutcomeTests(unittest.TestCase):
    def test_rename_outcome_preserves_api_payload_and_activity_fields(self) -> None:
        outcome = SourceActionOutcome(
            operation=SourceActionOperation.RENAME,
            status=SourceActionStatus.SUCCEEDED,
            scope="file",
            source_candidate_id="candidate-1",
            source_file_id="file-new",
            old_source_file_id="file-old",
            new_source_file_id="file-new",
            message="Renamed source file",
            file_count=1,
            total_size=12,
            old_path=Path("source/old.mkv"),
            new_path=Path("source/new.mkv"),
            exists_after_old=False,
            exists_after_new=True,
        )

        self.assertEqual(outcome.old_source_file_id, "file-old")
        self.assertEqual(outcome.new_source_file_id, "file-new")

        action = source_action_activity(self._session(), outcome)

        self.assertIsNotNone(action)
        self.assertEqual(action.operation, SourceActionOperation.RENAME)
        self.assertEqual(action.status, SourceActionStatus.SUCCEEDED)
        self.assertEqual(action.source_path, Path("source/old.mkv"))
        self.assertEqual(action.destination_path, Path("source/new.mkv"))
        self.assertEqual(action.context["affected_file_count"], 1)
        self.assertEqual(action.context["media_type"], "movie")

    def test_delete_outcome_preserves_api_payload_and_activity_fields(self) -> None:
        outcome = SourceActionOutcome(
            operation=SourceActionOperation.DELETE,
            status=SourceActionStatus.SUCCEEDED,
            scope="candidate",
            source_candidate_id="candidate-1",
            source_file_id=None,
            old_source_file_id=None,
            new_source_file_id=None,
            message="Deleted source candidate",
            file_count=3,
            total_size=120,
            old_path=Path("source/show"),
            new_path=None,
            exists_after=False,
            exists_after_old=False,
            exists_after_new=None,
        )

        self.assertEqual(outcome.file_count, 3)
        self.assertFalse(outcome.exists_after)

        action = source_action_activity(self._session(), outcome)

        self.assertIsNotNone(action)
        self.assertEqual(action.operation, SourceActionOperation.DELETE)
        self.assertEqual(action.status, SourceActionStatus.SUCCEEDED)
        self.assertEqual(action.source_path, Path("source/show"))
        self.assertIsNone(action.destination_path)
        self.assertEqual(action.context["total_size_bytes"], 120)

    def test_source_action_activity_rejects_payload_without_source_path(self) -> None:
        self.assertIsNone(source_action_activity(self._session(), {"operation": "delete"}))

    def test_source_action_activity_rejects_unknown_operation(self) -> None:
        self.assertIsNone(
            source_action_activity(self._session(), {"operation": "copy", "old_path": Path("source/file.mkv")})
        )

    def _session(self):
        return SimpleNamespace(
            id="session-1",
            origin_id="origin-1",
            path=Path("source"),
            media_type=MediaType.MOVIE,
        )


if __name__ == "__main__":
    unittest.main()
