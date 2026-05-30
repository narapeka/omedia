from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from app.api.http.deps import Transfer
from app.api.http.present.transfer import present_transfer_job
from app.api.http.schemas.common import DEFAULT_API_RESPONSES
from app.api.http.schemas.transfer import TransferJob, TransferRequest
from app.domain.transfer import TransferStatus

router = APIRouter(prefix="/transfer", tags=["transfer"], responses=DEFAULT_API_RESPONSES)


@router.get("/jobs", response_model=list[TransferJob])
def list_transfer_job_history(
    transfer: Transfer,
    depot_id: str | None = None,
    status: TransferStatus | None = None,
    requested_by: str | None = None,
    q: str | None = Query(default=None, min_length=1),
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
) -> list[TransferJob]:
    jobs = transfer.job_history(
        depot_id=depot_id,
        status=status,
        requested_by=requested_by,
        query=q,
        created_from=from_at,
        created_to=to_at,
        limit=limit,
        offset=offset,
    )
    return [present_transfer_job(job) for job in jobs]


@router.post("/jobs/{job_id}/cancel", response_model=TransferJob)
def cancel_transfer_job_run(job_id: str, transfer: Transfer) -> TransferJob:
    return present_transfer_job(transfer.cancel_job(job_id))


@router.post("/jobs", response_model=TransferJob)
def create_transfer_job(
    payload: TransferRequest,
    transfer: Transfer,
) -> TransferJob:
    job = transfer.request_depot_transfer(payload.depot_id, requested_by=payload.requested_by, candidate_ids=payload.candidate_ids)
    return present_transfer_job(job)
