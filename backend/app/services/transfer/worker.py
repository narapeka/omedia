from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.error import OmediaError
from app.domain.depot import Depot
from app.domain.media import DiskFileEntry
from app.domain.rule import TransferRule
from app.domain.transfer import TransferErrorCode, TransferJob
from app.infra.fs.move import move_with_replace
from app.services.transfer.queue import TransferJobQueue
from app.services.transfer.run import TransferExecutionResult, TransferRun


class TransferRejected(OmediaError):
    def __init__(self, code: TransferErrorCode, message: str, *, details: dict[str, object] | None = None):
        super().__init__(message)
        self.code = code
        self.details = {"transfer_error_code": code.value, **(details or {})}


@dataclass(frozen=True)
class TransferWorkerState:
    busy: bool = False
    current_job_id: str | None = None


class TransferWorker:
    def __init__(
        self,
        *,
        store,
        locks,
        activity,
        extensions,
        now=None,
    ):
        self.store = store
        self.locks = locks
        self.activity = activity
        self.extensions = extensions
        self.now = now or (lambda: datetime.now().astimezone())
        self.queue = TransferJobQueue(
            store=store,
            activity=activity,
            extensions=extensions,
            now=self.now,
        )
        self._busy_job_id: str | None = None

    @property
    def state(self) -> TransferWorkerState:
        return TransferWorkerState(
            busy=self._busy_job_id is not None,
            current_job_id=self._busy_job_id,
        )

    def create_job(self, depot: Depot, *, requested_by: str = "manual", candidate_ids: list[str] | None = None) -> TransferJob:
        return self.queue.create(depot, requested_by=requested_by, candidate_ids=candidate_ids)

    def execute(self, job: TransferJob, depot: Depot, *, transfer_rule: TransferRule | None = None) -> TransferExecutionResult:
        if self._busy_job_id is not None and self._busy_job_id != job.id:
            raise TransferRejected(
                TransferErrorCode.TRANSFER_WORKER_BUSY,
                "Transfer worker is busy",
                details={"active_job_id": self._busy_job_id, "job_id": job.id},
            )
        self._busy_job_id = job.id
        try:
            return self._run().execute(job, depot, transfer_rule=transfer_rule)
        finally:
            self._busy_job_id = None

    def build_plans(
        self,
        files: list[DiskFileEntry],
        depot: Depot,
        *,
        transfer_rule: TransferRule | None,
    ):
        return self._run().build_plans(files, depot, transfer_rule=transfer_rule)

    def _run(self) -> TransferRun:
        return TransferRun(
            store=self.store,
            locks=self.locks,
            activity=self.activity,
            extensions=self.extensions,
            now=self.now,
            move_files=move_with_replace,
        )
