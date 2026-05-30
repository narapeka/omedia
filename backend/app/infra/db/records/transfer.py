from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select

from app.infra.db.models.transfer import TransferJobModel
from app.infra.db.models.base import format_dt
from app.domain.transfer import TransferStatus
from app.domain.transfer import TransferJob


class TransferJobRecords:
    def save_transfer_job(self, job: TransferJob) -> None:
        with self.session_scope() as session:
            session.merge(TransferJobModel.from_domain(job))

    def get_transfer_job(self, job_id: str) -> TransferJob | None:
        with self.session_factory() as session:
            model = session.get(TransferJobModel, job_id)
            return model.to_domain() if model else None

    def list_transfer_jobs(
        self,
        *,
        depot_id: str | None = None,
        statuses: Sequence[TransferStatus] | None = None,
        requested_by: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int | None = None,
        offset: int | None = None,
        ordered: bool = False,
    ) -> list[TransferJob]:
        stmt = select(TransferJobModel)
        if depot_id:
            stmt = stmt.where(TransferJobModel.depot_id == depot_id)
        if statuses:
            stmt = stmt.where(TransferJobModel.status.in_([status.value for status in statuses]))
        if requested_by:
            stmt = stmt.where(TransferJobModel.requested_by == requested_by)
        if created_from:
            stmt = stmt.where(TransferJobModel.created_at >= format_dt(created_from))
        if created_to:
            stmt = stmt.where(TransferJobModel.created_at <= format_dt(created_to))
        if ordered:
            stmt = stmt.order_by(TransferJobModel.created_at, TransferJobModel.id)
        else:
            stmt = stmt.order_by(TransferJobModel.created_at.desc(), TransferJobModel.id)
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)
        with self.session_factory() as session:
            return [model.to_domain() for model in session.scalars(stmt).all()]

    def active_transfer_job_for_depot(self, depot_id: str) -> TransferJob | None:
        jobs = self.list_transfer_jobs(
            depot_id=depot_id,
            statuses=[TransferStatus.QUEUED, TransferStatus.RUNNING, TransferStatus.CANCELLING],
            limit=1,
        )
        return jobs[0] if jobs else None

    def active_transfer_job(self) -> TransferJob | None:
        jobs = self.list_transfer_jobs(
            statuses=[TransferStatus.QUEUED, TransferStatus.RUNNING, TransferStatus.CANCELLING],
            limit=1,
        )
        return jobs[0] if jobs else None

    def next_queued_transfer_job(self) -> TransferJob | None:
        jobs = self.list_transfer_jobs(statuses=[TransferStatus.QUEUED], ordered=True)
        if not jobs:
            return None
        return jobs[0]
