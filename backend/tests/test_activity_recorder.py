from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.domain.activity import ActivityArea, ActivityEntityType, ActivityStatus
from app.domain.media import MediaType
from app.domain.origin import OriginTrigger
from app.domain.transfer import TransferStatus
from app.domain.origin import OrganizePolicy, Origin
from app.domain.depot import Depot, TransferPolicy
from app.domain.transfer import TransferJob
from app.services.activity.recorder import ActivityRecorder
from support import FakeActivityStore


class ActivityRecorderTests(unittest.TestCase):
    def test_file_helpers_persist_generic_entity_source_and_target(self) -> None:
        store = FakeActivityStore()
        recorder = ActivityRecorder(store, id_factory=id_factory(), now=fixed_now)
        origin = _origin()
        depot = _depot()
        source = Path("C:/drop/Avatar.mkv")
        target = Path("C:/Depot/Avatar.mkv")

        moved = recorder.record_depot_item(
            area=ActivityArea.MANUAL_ORGANIZE,
            status=ActivityStatus.SUCCEEDED,
            source_path=source,
            destination_path=target,
            origin=origin,
            depot=depot,
            context={"tmdb_id": 19995},
        )
        renamed = recorder.record_rename(
            source_path=source,
            destination_path=target,
            status=ActivityStatus.SUCCEEDED,
            origin=origin,
        )
        deleted = recorder.record_delete(
            source_path=source,
            status=ActivityStatus.SUCCEEDED,
            origin=origin,
        )

        self.assertEqual(moved.entity_source, str(source))
        self.assertEqual(moved.entity_target, str(target))
        self.assertEqual(moved.origin_id, origin.id)
        self.assertEqual(moved.depot_id, depot.id)
        self.assertEqual(moved.tmdb_id, "19995")
        self.assertEqual(renamed.entity_source, str(source))
        self.assertEqual(renamed.entity_target, str(target))
        self.assertEqual(deleted.entity_source, str(source))
        self.assertIsNone(deleted.entity_target)
        self.assertFalse(hasattr(moved, "entity_name"))
        self.assertFalse(hasattr(moved, "source_path"))
        self.assertFalse(hasattr(moved, "destination_path"))

    def test_lifecycle_helpers_persist_generic_entity_source_and_target(self) -> None:
        store = FakeActivityStore()
        recorder = ActivityRecorder(store, id_factory=id_factory(), now=fixed_now)
        origin = _origin()
        depot = _depot()
        job = TransferJob(id="transfer-1", depot_id=depot.id, status=TransferStatus.QUEUED)

        session = recorder.record_session_event(
            area=ActivityArea.MANUAL_ORGANIZE,
            entity_type=ActivityEntityType.ORGANIZE_SESSION,
            action="move_to_depot",
            status=ActivityStatus.FAILED,
            trace_id="session-1",
            origin=origin,
            depot=depot,
        )
        transfer = recorder.record_transfer_job_event(
            job=job,
            depot=depot,
            status=ActivityStatus.QUEUED,
        )

        self.assertEqual(session.entity_source, origin.name)
        self.assertEqual(session.entity_target, depot.name)
        self.assertEqual(session.trace_id, "session-1")
        self.assertEqual(transfer.entity_source, str(depot.path))
        self.assertEqual(transfer.entity_target, str(depot.policy.target_library_path))
        self.assertEqual(transfer.trace_id, job.id)
        self.assertEqual([event.id for event in store.events], ["activity-1", "activity-2"])


def id_factory():
    counter = 0

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"activity-{counter}"

    return next_id


def fixed_now() -> datetime:
    return datetime(2026, 5, 18, tzinfo=timezone.utc)


def _origin() -> Origin:
    return Origin(
        id="origin-movie",
        name="Movie Origin",
        path=Path("C:/drop"),
        media_type=MediaType.MOVIE,
        trigger=OriginTrigger.MANUAL,
        policy=OrganizePolicy(target_depot_id="Depot-movie"),
    )


def _depot() -> Depot:
    return Depot(
        id="Depot-movie",
        name="Movie Depot",
        path=Path("C:/Depot"),
        media_type=MediaType.MOVIE,
        policy=TransferPolicy(target_library_path=Path("C:/library")),
    )


if __name__ == "__main__":
    unittest.main()
