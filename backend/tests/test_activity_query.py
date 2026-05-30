from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.services.activity.query import ActivityQueryService
from app.infra.db.store import Store
from app.domain.activity import ActivityAction, ActivityArea, ActivityEntityType, ActivityEvent, ActivityStatus
from app.domain.media import MediaType
from app.domain.depot import Depot, TransferPolicy
from support import FakeActivityStore


class ActivityQueryTests(unittest.TestCase):
    def test_list_activity_maps_group_and_filters_to_store(self) -> None:
        store = FakeActivityStore([activity_event("matching")])

        events = ActivityQueryService(store).list_activity(
            group="organize",
            areas=[ActivityArea.MANUAL_ORGANIZE],
            action=ActivityAction.MOVE_TO_DEPOT,
            status=ActivityStatus.SUCCEEDED,
            reason="source_missing",
            origin_id="manual",
            depot_id="Depot",
            library_path=Path("C:/library"),
            media_type="movie",
            tmdb_id="42",
            focus="attention",
            q="Avatar",
            time_from=datetime(2026, 5, 1, tzinfo=timezone.utc),
            time_to=datetime(2026, 5, 3, tzinfo=timezone.utc),
            limit=1,
            offset=2,
        )

        self.assertEqual([event.id for event in events], ["matching"])
        self.assertEqual(
            store.calls[0],
            {
                "areas": (
                    ActivityArea.MANUAL_ORGANIZE,
                ),
                "entity_type": None,
                "action": ActivityAction.MOVE_TO_DEPOT,
                "status": ActivityStatus.SUCCEEDED,
                "reason": "source_missing",
                "origin_id": "manual",
                "depot_id": "Depot",
                "library_path": str(Path("C:/library")),
                "media_type": "movie",
                "tmdb_id": "42",
                "focus": "attention",
                "q": "Avatar",
                "time_from": datetime(2026, 5, 1, tzinfo=timezone.utc),
                "time_to": datetime(2026, 5, 3, tzinfo=timezone.utc),
                "limit": 1,
                "offset": 2,
            },
        )

    def test_list_activity_intersects_explicit_area_with_group(self) -> None:
        store = FakeActivityStore([activity_event("matching")])

        events = ActivityQueryService(store).list_activity(
            group="organize",
            areas=[ActivityArea.MANUAL_TRANSFER],
        )

        self.assertEqual(events, [])
        self.assertEqual(store.calls, [])

    def test_activity_event_persistence_filters_searches_and_paginates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "state.sqlite")
            store.initialize()
            try:
                store.save_activity_event(
                    activity_event(
                        "older",
                        time=datetime(2026, 5, 1, tzinfo=timezone.utc),
                        entity_source=Path("C:/drop/Avatar.mkv"),
                        entity_target=Path("C:/Depot/Avatar.mkv"),
                        origin_id="manual",
                        tmdb_id="19995",
                        context={"metadata": {"title": "Avatar"}, "legacy_job_id": "secret-match"},
                    ),
                )
                store.save_activity_event(
                    activity_event(
                        "newer",
                        time=datetime(2026, 5, 3, tzinfo=timezone.utc),
                        entity_source=Path("C:/drop/Avatar.2.mkv"),
                        entity_target=Path("C:/Depot/Avatar.2.mkv"),
                        origin_id="manual",
                        tmdb_id="19995",
                        context={"metadata": {"title": "Avatar"}},
                    ),
                )
                store.save_activity_event(
                    activity_event(
                        "job-only",
                        time=datetime(2026, 5, 4, tzinfo=timezone.utc),
                        entity_source=Path("C:/drop/Other.mkv"),
                        entity_target=Path("C:/Depot/Other.mkv"),
                        origin_id="manual",
                        tmdb_id="7",
                        context={"legacy_job_id": "Avatar"},
                    ),
                )

                events = store.list_activity_events(
                    areas=[ActivityArea.MANUAL_ORGANIZE],
                    action=ActivityAction.MOVE_TO_DEPOT,
                    status=ActivityStatus.SUCCEEDED,
                    origin_id="manual",
                    tmdb_id="19995",
                    q="Avatar",
                    time_from=datetime(2026, 5, 1, tzinfo=timezone.utc),
                    time_to=datetime(2026, 5, 3, 23, 59, tzinfo=timezone.utc),
                    offset=1,
                    limit=1,
                )

                self.assertEqual([event.id for event in events], ["older"])
            finally:
                store.close()

    def test_activity_event_focus_filters_are_applied_before_pagination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "state.sqlite")
            store.initialize()
            try:
                store.save_activity_event(
                    activity_event(
                        "normal-newest",
                        time=datetime(2026, 5, 5, tzinfo=timezone.utc),
                    ),
                )
                store.save_activity_event(
                    activity_event(
                        "failed",
                        status=ActivityStatus.FAILED,
                        time=datetime(2026, 5, 4, tzinfo=timezone.utc),
                    ),
                )
                store.save_activity_event(
                    activity_event(
                        "unmatched",
                        area=ActivityArea.WATCH_ORGANIZE,
                        action=ActivityAction.RETURN,
                        reason="unmatched",
                        time=datetime(2026, 5, 3, tzinfo=timezone.utc),
                    ),
                )

                attention = store.list_activity_events(focus="attention", limit=1)
                unmatched = store.list_activity_events(focus="unmatched", limit=10)
                failed = store.list_activity_events(focus="failed", limit=10)

                self.assertEqual([event.id for event in attention], ["failed"])
                self.assertEqual([event.id for event in unmatched], ["unmatched"])
                self.assertEqual([event.id for event in failed], ["failed"])
            finally:
                store.close()

    def test_provenance_for_path_deduplicates_and_sorts_newest_first(self) -> None:
        path = Path("C:/media/Depot/Movie.mkv")
        older = activity_event(
            "older",
            entity_source=Path("C:/drop/Movie.mkv"),
            entity_target=path,
            time=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
        newer = activity_event(
            "newer",
            entity_source=path,
            entity_target=Path("C:/library/Movie.mkv"),
            area=ActivityArea.MANUAL_TRANSFER,
            action=ActivityAction.TRANSFER,
            time=datetime(2026, 5, 2, tzinfo=timezone.utc),
        )
        duplicate_newer = activity_event(
            "newer",
            entity_source=path,
            entity_target=Path("C:/library/Movie.mkv"),
            area=ActivityArea.MANUAL_TRANSFER,
            action=ActivityAction.TRANSFER,
            time=datetime(2026, 5, 2, tzinfo=timezone.utc),
        )
        store = FakeActivityStore([], by_source=[newer], by_target=[older, duplicate_newer])

        events = ActivityQueryService(store).provenance_for_path(path)

        self.assertEqual([event.id for event in events], ["newer", "older"])

    def test_depot_file_provenance_resolves_relative_path_under_depot(self) -> None:
        depot = Depot(
            id="Depot",
            name="Movie Depot",
            path=Path("C:/Depot"),
            media_type=MediaType.MOVIE,
            policy=TransferPolicy(target_library_path=Path("C:/library")),
        )
        event = activity_event("entry", entity_source=Path("C:/drop/Movie.mkv"), entity_target=depot.path / "Movie.mkv")
        store = FakeActivityStore([], by_target=[event])

        events = ActivityQueryService(store).depot_file_provenance(depot, Path("Movie.mkv"))

        self.assertEqual([item.id for item in events], ["entry"])


def activity_event(
    event_id: str,
    *,
    area: ActivityArea = ActivityArea.MANUAL_ORGANIZE,
    action: ActivityAction = ActivityAction.MOVE_TO_DEPOT,
    status: ActivityStatus = ActivityStatus.SUCCEEDED,
    time: datetime | None = None,
    entity_source: str | Path | None = None,
    entity_target: str | Path | None = None,
    origin_id: str | None = None,
    tmdb_id: str | None = None,
    reason: str | None = None,
    context: dict | None = None,
) -> ActivityEvent:
    return ActivityEvent(
        id=event_id,
        time=time or datetime(2026, 5, 1, tzinfo=timezone.utc),
        area=area,
        entity_type=ActivityEntityType.FILE,
        action=action,
        status=status,
        reason=reason,
        entity_source=str(entity_source) if entity_source is not None else "Avatar.mkv",
        entity_target=str(entity_target) if entity_target is not None else None,
        media_type="movie",
        tmdb_id=tmdb_id,
        origin_id=origin_id,
        context=context or {},
    )


if __name__ == "__main__":
    unittest.main()
