from __future__ import annotations

import threading
from datetime import datetime

from app.core.error import ConfigurationError
from app.infra.log.app import app_log
from app.domain.activity import ActivityAction, ActivityStatus
from app.domain.transfer import TransferErrorCode, TransferStatus
from app.domain.depot import Depot
from app.domain.runtime import WorkerStatus
from app.domain.transfer import TransferJob
from app.services.transfer.worker import TransferExecutionResult, TransferRejected, TransferWorker, TransferWorkerState


CRON_FIELD_RANGES = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day", 1, 31),
    ("month", 1, 12),
    ("weekday", 0, 6),
)


class TransferScheduler:
    def __init__(self) -> None:
        self._last_enqueued_minute_by_depot: dict[str, str] = {}

    def due_depots(self, depots: list[Depot], *, now: datetime | None = None) -> list[Depot]:
        current = (now or datetime.now().astimezone()).astimezone()
        minute_key = current.strftime("%Y-%m-%dT%H:%M%z")
        due: list[Depot] = []
        for depot in depots:
            if not depot.enabled or depot.policy.trigger.value != "scheduled" or not depot.policy.schedule:
                continue
            if self._last_enqueued_minute_by_depot.get(depot.id) == minute_key:
                continue
            if cron_matches(depot.policy.schedule, current):
                self._last_enqueued_minute_by_depot[depot.id] = minute_key
                due.append(depot)
        return due


class TransferService:
    """Coordinates Depot-to-Library Transfer jobs around the low-level worker."""

    def __init__(
        self,
        *,
        configuration,
        worker: TransferWorker,
        poll_interval_seconds: float = 60.0,
        scheduler: TransferScheduler | None = None,
    ):
        self.configuration = configuration
        self.worker = worker
        self.poll_interval_seconds = poll_interval_seconds
        self.scheduler = scheduler or TransferScheduler()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._started_at: datetime | None = None
        self._updated_at: datetime | None = None
        self._last_error: str | None = None

    @property
    def state(self) -> TransferWorkerState:
        return self.worker.state

    def start(self) -> None:
        with self._lock:
            self.recover_stale_running_jobs()
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_poll_loop, name="omedia-transfer-worker", daemon=True)
            self._thread.start()
            self._started_at = self._started_at or _now()
            self._updated_at = _now()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5)
        with self._lock:
            self._thread = None
            self._updated_at = _now()

    def status(self) -> WorkerStatus:
        worker_state = self.worker.state
        running = bool(self._thread and self._thread.is_alive())
        if self._last_error:
            state = "error"
        elif worker_state.busy:
            state = "running"
        elif running:
            state = "idle"
        else:
            state = "stopped"
        return WorkerStatus(
            id="transfer",
            label="Transfer",
            running=running,
            state=state,
            current_item_id=worker_state.current_job_id,
            last_error=self._last_error,
            started_at=self._started_at,
            updated_at=self._updated_at,
        )

    def list_jobs(
        self,
        *,
        depot_id: str | None = None,
        statuses: list[TransferStatus] | None = None,
        requested_by: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int | None = 100,
        offset: int | None = None,
    ) -> list[TransferJob]:
        return self.worker.store.list_transfer_jobs(
            depot_id=depot_id,
            statuses=statuses,
            requested_by=requested_by,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
            offset=offset,
        )

    def job_history(
        self,
        *,
        depot_id: str | None = None,
        status: TransferStatus | None = None,
        requested_by: str | None = None,
        query: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TransferJob]:
        jobs = self.list_jobs(
            depot_id=depot_id,
            statuses=[status] if status else None,
            requested_by=requested_by,
            created_from=created_from,
            created_to=created_to,
            limit=None,
        )
        depot_by_id = {depot.id: depot for depot in self.configuration.list_depots()}
        filtered = [job for job in jobs if _matches_transfer_query(job, depot_by_id.get(job.depot_id), query)]
        return filtered[offset:offset + limit]

    def request_depot_transfer(self, depot_id: str, *, requested_by: str = "manual", candidate_ids: list[str] | None = None) -> TransferJob:
        return self.enqueue(self._depot_by_id(depot_id), requested_by=requested_by, candidate_ids=candidate_ids)

    def enqueue(self, depot: Depot, *, requested_by: str = "manual", candidate_ids: list[str] | None = None) -> TransferJob:
        job = self.worker.create_job(depot, requested_by=requested_by, candidate_ids=candidate_ids)
        self._wake_event.set()
        return job

    def cancel_job(self, job_id: str) -> TransferJob:
        job = self.worker.store.get_transfer_job(job_id)
        if job is None:
            raise ConfigurationError(
                f"Unknown TransferJob: {job_id}",
                code="transfer_job.unknown",
                details={"job_id": job_id},
            )
        if job.status == TransferStatus.QUEUED:
            job.status = TransferStatus.CANCELLED
            job.message = "Transfer cancelled before it started"
            job.finished_at = _now()
            self.worker.store.save_transfer_job(job)
            try:
                depot = self._depot_by_id(job.depot_id)
            except Exception:
                depot = None
            self.worker.activity.record_transfer_job_event(
                job=job,
                depot=depot,
                action=ActivityAction.CANCEL,
                status=ActivityStatus.SUCCEEDED,
                reason="user_cancelled",
                summary="Transfer cancelled before it started",
            )
        elif job.status == TransferStatus.RUNNING:
            job.status = TransferStatus.CANCELLING
            job.message = "Transfer cancellation requested"
            self.worker.store.save_transfer_job(job)
            app_log.info("transfer.cancel", "Transfer cancellation requested", trace_id=job.id, depot_id=job.depot_id)
        self._wake_event.set()
        return job

    def execute_depot(self, depot: Depot, *, requested_by: str = "manual") -> TransferExecutionResult:
        job = self.worker.create_job(depot, requested_by=requested_by)
        return self.worker.execute(job, depot, transfer_rule=self._transfer_rule_for_depot(depot))

    def poll_once(self, *, now: datetime | None = None) -> list[TransferExecutionResult]:
        results: list[TransferExecutionResult] = []
        for depot in self.scheduler.due_depots(self.configuration.list_depots(), now=now):
            try:
                self.worker.create_job(depot, requested_by="schedule")
            except TransferRejected:
                continue
        return results

    def run_queued_once(self) -> TransferExecutionResult | None:
        job = self.worker.store.next_queued_transfer_job()
        if not job:
            return None
        try:
            depot = self._depot_by_id(job.depot_id)
        except Exception as exc:
            return self._fail_unresolvable_job(job, exc)
        return self.worker.execute(job, depot, transfer_rule=self._transfer_rule_for_depot(depot))

    def recover_stale_running_jobs(self) -> list[TransferJob]:
        recovered: list[TransferJob] = []
        for job in self.worker.store.list_transfer_jobs(statuses=[TransferStatus.RUNNING, TransferStatus.CANCELLING]):
            job.status = TransferStatus.FAILED
            job.error_code = TransferErrorCode.INTERRUPTED
            job.message = "Backend stopped while this transfer was running"
            job.finished_at = _now()
            self.worker.store.save_transfer_job(job)
            try:
                depot = self._depot_by_id(job.depot_id)
            except Exception:
                depot = None
            self.worker.activity.record_transfer_job_event(
                job=job,
                depot=depot,
                status=ActivityStatus.FAILED,
                reason="interrupted",
                summary=job.message,
            )
            recovered.append(job)
        return recovered

    def _transfer_rule_for_depot(self, depot: Depot):
        return self.worker.store.get_transfer_rule(depot.policy.transfer_rule_id) if depot.policy.transfer_rule_id else None

    def _run_poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.poll_once()
                while True:
                    result = self.run_queued_once()
                    if result is None:
                        break
                    if result.hard_timeout_stop:
                        break
                self._last_error = None
                self._updated_at = _now()
            except Exception as exc:
                self._last_error = str(exc)
                self._updated_at = _now()
            if self._stop_event.is_set():
                return
            self._wake_event.wait(self.poll_interval_seconds)
            self._wake_event.clear()

    def _depot_by_id(self, depot_id: str) -> Depot:
        if hasattr(self.configuration, "get_depot"):
            return self.configuration.get_depot(depot_id)
        for depot in self.configuration.list_depots():
            if depot.id == depot_id:
                return depot
        raise TransferRejected(
            TransferErrorCode.MOVE_FAILED,
            f"Depot no longer exists: {depot_id}",
            details={"depot_id": depot_id},
        )

    def _fail_unresolvable_job(self, job: TransferJob, exc: Exception) -> TransferExecutionResult:
        job.status = TransferStatus.FAILED
        job.error_code = TransferErrorCode.MOVE_FAILED
        job.message = str(exc)
        job.started_at = job.started_at or self.worker.now()
        job.finished_at = self.worker.now()
        self.worker.store.save_transfer_job(job)
        app_log.exception("transfer.worker", "Queued transfer job failed before execution", exc=exc, trace_id=job.id, depot_id=job.depot_id)
        entry = self.worker.activity.record_transfer_job_event(
            job=job,
            status=ActivityStatus.FAILED,
            reason="invalid_destination",
            summary=str(exc),
            context={
                "depot_id": job.depot_id,
                "error_type": type(exc).__name__,
            },
        )
        return TransferExecutionResult(job=job, failed=1, activity_events=[entry])

def _now() -> datetime:
    return datetime.now().astimezone()


def _matches_transfer_query(job: TransferJob, depot: Depot | None, query: str | None) -> bool:
    if not query or not query.strip():
        return True
    needle = query.strip().casefold()
    values = [
        depot.name if depot else "",
        str(depot.path) if depot else "",
        str(depot.policy.target_library_path) if depot else "",
        job.status.value,
        job.requested_by,
        job.message or "",
        job.error_code.value if job.error_code else "",
    ]
    return any(needle in value.casefold() for value in values if value)


def cron_matches(schedule: str, value: datetime) -> bool:
    try:
        validate_cron_schedule(schedule)
    except ConfigurationError:
        return False
    fields = schedule.split()
    minute, hour, day, month, weekday = fields
    return (
        _field_matches(minute, value.minute)
        and _field_matches(hour, value.hour)
        and _field_matches(day, value.day)
        and _field_matches(month, value.month)
        and _field_matches(weekday, value.weekday())
    )


def validate_cron_schedule(schedule: str) -> None:
    fields = schedule.split()
    if len(fields) != len(CRON_FIELD_RANGES):
        raise _cron_error("Transfer schedule must have five cron fields: minute hour day month weekday", schedule=schedule)
    for field, (name, minimum, maximum) in zip(fields, CRON_FIELD_RANGES):
        _validate_cron_field(name, field, minimum=minimum, maximum=maximum)


def _validate_cron_field(name: str, field: str, *, minimum: int, maximum: int) -> None:
    if field == "*":
        return
    for part in field.split(","):
        if not part:
            raise _cron_error(f"Transfer schedule {name} field has an empty value", field=name)
        if part.startswith("*/"):
            step = _parse_cron_int(name, part[2:], part)
            if step <= 0:
                raise _cron_error(f"Transfer schedule {name} step must be greater than 0", field=name, value=part)
            continue
        if "/" in part:
            raise _cron_error(f"Transfer schedule {name} field uses unsupported step syntax: {part}", field=name, value=part)
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = _parse_cron_int(name, start_text, part)
            end = _parse_cron_int(name, end_text, part)
            _ensure_cron_range(name, start, minimum=minimum, maximum=maximum)
            _ensure_cron_range(name, end, minimum=minimum, maximum=maximum)
            if start > end:
                raise _cron_error(f"Transfer schedule {name} range must not be reversed: {part}", field=name, value=part)
            continue
        value = _parse_cron_int(name, part, part)
        _ensure_cron_range(name, value, minimum=minimum, maximum=maximum)


def _parse_cron_int(name: str, text: str, field: str) -> int:
    try:
        return int(text)
    except ValueError as exc:
        raise _cron_error(f"Transfer schedule {name} field must be an integer: {field}", field=name, value=field) from exc


def _ensure_cron_range(name: str, value: int, *, minimum: int, maximum: int) -> None:
    if value < minimum or value > maximum:
        raise _cron_error(
            f"Transfer schedule {name} value must be between {minimum} and {maximum}: {value}",
            field=name,
            value=value,
            minimum=minimum,
            maximum=maximum,
        )


def _cron_error(message: str, **details) -> ConfigurationError:
    return ConfigurationError(message, code="transfer_schedule.invalid", details=details)


def _field_matches(field: str, value: int) -> bool:
    if field == "*":
        return True
    return any(_single_field_matches(part, value) for part in field.split(","))


def _single_field_matches(field: str, value: int) -> bool:
    if field.startswith("*/"):
        return value % int(field[2:]) == 0
    if "-" in field:
        start, end = field.split("-", 1)
        return int(start) <= value <= int(end)
    return int(field) == value
