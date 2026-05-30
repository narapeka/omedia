from __future__ import annotations

from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.models.base import Base, dump_json, format_dt, load_json, parse_dt
from app.domain.transfer import TransferErrorCode, TransferStatus
from app.domain.transfer import TransferJob


class TransferJobModel(Base):
    __tablename__ = "transfer_jobs"
    __table_args__ = (
        Index("idx_transfer_jobs_depot_id", "depot_id"),
        Index("idx_transfer_jobs_status", "status"),
        Index("idx_transfer_jobs_created_at", "created_at"),
        Index("idx_transfer_jobs_requested_by", "requested_by"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    depot_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    @classmethod
    def from_domain(cls, job: TransferJob) -> "TransferJobModel":
        return cls(
            id=job.id,
            depot_id=job.depot_id,
            status=job.status.value,
            requested_by=job.requested_by,
            error_code=job.error_code.value if job.error_code else None,
            created_at=format_dt(job.created_at),
            started_at=format_dt(job.started_at),
            finished_at=format_dt(job.finished_at),
            message=job.message,
            metadata_json=dump_json(job.metadata),
        )

    def to_domain(self) -> TransferJob:
        return TransferJob(
            id=self.id,
            depot_id=self.depot_id,
            status=TransferStatus(self.status),
            requested_by=self.requested_by,
            error_code=TransferErrorCode(self.error_code) if self.error_code else None,
            created_at=parse_dt(self.created_at),
            started_at=parse_dt(self.started_at),
            finished_at=parse_dt(self.finished_at),
            message=self.message,
            metadata=load_json(self.metadata_json) or {},
        )
