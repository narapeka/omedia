from __future__ import annotations

import time
from datetime import datetime
from uuid import uuid4

from app.domain.activity import ActivityStatus
from app.domain.depot import Depot
from app.domain.transfer import TransferErrorCode, TransferJob
from app.services.depot.candidate import CandidateBook


class TransferJobQueue:
    def __init__(self, *, store, activity, extensions, now=None):
        self.store = store
        self.activity = activity
        self.extensions = extensions
        self.now = now or (lambda: datetime.now().astimezone())

    def create(self, depot: Depot, *, requested_by: str = "manual", candidate_ids: list[str] | None = None) -> TransferJob:
        if self.store.active_transfer_job_for_depot(depot.id):
            from app.services.transfer.worker import TransferRejected

            raise TransferRejected(
                TransferErrorCode.DEPOT_TRANSFER_BUSY,
                "Depot already has pending or running transfer",
                details={"depot_id": depot.id, "depot_name": depot_name(depot)},
            )
        metadata: dict[str, object] = {}
        if candidate_ids:
            book = CandidateBook(depot, self.extensions)
            candidates = book.many(candidate_ids)
            metadata["candidate_scope"] = [book.scope(candidate).as_dict() for candidate in candidates]
            metadata["candidate_ids"] = list(candidate_ids)
        job = TransferJob(
            id=f"transfer-{time.time_ns()}-{uuid4().hex}",
            depot_id=depot.id,
            requested_by=requested_by,
            created_at=self.now(),
            metadata=metadata,
        )
        self.store.save_transfer_job(job)
        self.activity.record_transfer_job_event(
            job=job,
            depot=depot,
            status=ActivityStatus.QUEUED,
            summary=f"Transfer queued for {depot_name(depot)} Depot",
            context=metadata,
        )
        return job


def depot_name(depot: Depot) -> str:
    return depot.name or depot.id
