from __future__ import annotations

from app.api.http.schemas.transfer import TransferJob


def present_transfer_job(job) -> TransferJob:
    return TransferJob(
        id=job.id,
        depot_id=job.depot_id,
        status=job.status,
        requested_by=job.requested_by,
        error_code=job.error_code,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        message=job.message,
        metadata=dict(job.metadata or {}),
    )
