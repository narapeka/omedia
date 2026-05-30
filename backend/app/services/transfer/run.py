from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.domain.activity import ActivityAction, ActivityArea, ActivityEvent, ActivityStatus
from app.domain.depot import Depot
from app.domain.media import DiskFileEntry
from app.domain.rule import TransferRule
from app.domain.transfer import TransferErrorCode, TransferJob, TransferStatus
from app.engines.rule.transfer import TransferRuleEngine
from app.engines.scan.depot import expand_depot_candidate_files, scan_depot_candidates
from app.infra.fs.constants import CONSECUTIVE_TIMEOUT_LIMIT
from app.infra.fs.move import move_with_replace
from app.infra.fs.result import StorageMoveStatus
from app.infra.log.app import app_log
from app.services.depot.candidate import CandidateBook, CandidateScope
from app.services.transfer.plan import (
    TransferPlan,
    TransferPlanBlock,
    build_plan,
    plan_context,
    plan_key,
    prepare_replace_roots,
)
from app.services.transfer.queue import depot_name


@dataclass
class TransferSummary:
    moved: int = 0
    skipped: int = 0
    failed: int = 0
    timed_out: int = 0
    consecutive_timeouts: int = 0
    hard_timeout_stop: bool = False
    activity_events: list[ActivityEvent] = field(default_factory=list)

    def job_message(self, *, cancelled: bool = False) -> str:
        message = f"moved={self.moved} skipped={self.skipped} failed={self.failed} timed_out={self.timed_out}"
        return f"cancelled {message}" if cancelled else message

    def text(self, *, cancelled: bool = False) -> str:
        pieces = [
            self._label(self.moved, "file transferred", "files transferred"),
            self._label(self.skipped, "skipped", "skipped"),
            self._label(self.failed, "failed", "failed"),
            self._label(self.timed_out, "timed out", "timed out"),
        ]
        text = ", ".join(piece for piece in pieces if piece)
        if not text:
            text = "No files transferred"
        return f"Transfer cancelled after {text}" if cancelled else text

    def status(self) -> TransferStatus:
        if self.failed:
            return TransferStatus.FAILED
        return TransferStatus.SUCCEEDED if self.moved else TransferStatus.SKIPPED

    def activity_status(self) -> ActivityStatus:
        if self.failed:
            return ActivityStatus.FAILED
        return ActivityStatus.SUCCEEDED if self.moved else ActivityStatus.SKIPPED

    def error_code(self) -> TransferErrorCode | None:
        return TransferErrorCode.MOVE_FAILED if self.failed else None

    def reason(self) -> str | None:
        if self.hard_timeout_stop:
            return "hard_timeout_stop"
        return "no_files" if not self.moved and self.skipped else None

    def context(self) -> dict[str, object]:
        return {
            "moved": self.moved,
            "skipped": self.skipped,
            "failed": self.failed,
            "timed_out": self.timed_out,
            "hard_timeout_stop": self.hard_timeout_stop,
        }

    @staticmethod
    def _label(count: int, singular: str, plural: str) -> str | None:
        if count <= 0:
            return None
        return f"{count} {singular if count == 1 else plural}"


@dataclass(frozen=True)
class TransferExecutionResult:
    job: TransferJob
    moved: int = 0
    skipped: int = 0
    failed: int = 0
    timed_out: int = 0
    hard_timeout_stop: bool = False
    activity_events: list[ActivityEvent] = field(default_factory=list)


class TransferEventLog:
    def __init__(self, activity):
        self.activity = activity

    def started(self, job: TransferJob, depot: Depot) -> None:
        self.activity.record_transfer_job_event(
            job=job,
            depot=depot,
            status=ActivityStatus.STARTED,
            summary=f"Transfer started for {depot_name(depot)} Depot",
        )

    def missing_scope(
        self,
        summary: TransferSummary,
        *,
        job: TransferJob,
        depot: Depot,
        missing_scope: CandidateScope,
    ) -> None:
        relative_path = missing_scope.relative_path or Path("")
        self._append_item(
            summary,
            job=job,
            depot=depot,
            status=ActivityStatus.SKIPPED,
            reason="source_missing",
            source_path=depot.path / relative_path,
            destination_path=depot.policy.target_library_path,
            summary_text="Selected Depot candidate is missing",
            context={
                "depot_id": depot.id,
                "depot_name": depot.name,
                "depot_path": str(depot.path),
                "target_library_path": str(depot.policy.target_library_path),
                "depot_candidate_id": missing_scope.id,
                "depot_candidate_kind": missing_scope.kind,
                "depot_relative_path": missing_scope.relative_path_text,
                "candidate_group_key": missing_scope.group_key,
                "organize_prefix": missing_scope.organize_prefix_text,
                "media_relative_path": missing_scope.media_relative_path_text,
                "media_type": depot.media_type.value,
            },
        )
        summary.skipped += 1

    def plan_block(
        self,
        summary: TransferSummary,
        *,
        job: TransferJob,
        depot: Depot,
        plan: TransferPlan,
        plan_block: TransferPlanBlock,
        context: dict,
    ) -> None:
        self._append_item(
            summary,
            job=job,
            depot=depot,
            status=plan_block.status,
            reason=plan_block.reason,
            source_path=plan.file.path,
            destination_path=plan.destination,
            summary_text=plan_block.summary,
            context={**context, **plan_block.context, "blocked_reason": plan_block.reason},
        )
        if plan_block.status == ActivityStatus.FAILED:
            summary.failed += 1
            summary.consecutive_timeouts = 0
        else:
            summary.skipped += 1

    def plan_success(
        self,
        summary: TransferSummary,
        *,
        job: TransferJob,
        depot: Depot,
        plan: TransferPlan,
        context: dict,
    ) -> None:
        overwritten = plan.destination_preexisting or plan.destination.exists()
        self._append_item(
            summary,
            job=job,
            depot=depot,
            status=ActivityStatus.SUCCEEDED,
            source_path=plan.file.path,
            destination_path=plan.destination,
            summary_text="Transferred with replacement" if overwritten else "Transferred",
            context=context,
        )
        summary.moved += 1
        summary.consecutive_timeouts = 0

    def plan_timeout(
        self,
        summary: TransferSummary,
        *,
        job: TransferJob,
        depot: Depot,
        plan: TransferPlan,
        move_result,
        context: dict,
    ) -> None:
        self._append_item(
            summary,
            job=job,
            depot=depot,
            status=ActivityStatus.FAILED,
            reason="timed_out",
            source_path=plan.file.path,
            destination_path=plan.destination,
            summary_text=move_result.message,
            context={**context, "error_type": move_result.error_type},
        )
        summary.skipped += 1
        summary.timed_out += 1
        summary.consecutive_timeouts += 1

    def plan_failure(
        self,
        summary: TransferSummary,
        *,
        job: TransferJob,
        depot: Depot,
        plan: TransferPlan,
        move_result,
        context: dict,
    ) -> None:
        self._append_item(
            summary,
            job=job,
            depot=depot,
            status=ActivityStatus.FAILED,
            reason=move_result.error_type,
            source_path=plan.file.path,
            destination_path=plan.destination,
            summary_text=move_result.message,
            context={**context, "error_type": move_result.error_type},
        )
        summary.failed += 1
        summary.consecutive_timeouts = 0

    def plan_exception(
        self,
        summary: TransferSummary,
        *,
        job: TransferJob,
        depot: Depot,
        plan: TransferPlan,
        context: dict,
        exc: Exception,
    ) -> None:
        app_log.exception(
            "transfer.worker",
            "Transfer file failed",
            exc=exc,
            trace_id=job.id,
            source_path=plan.file.path,
            destination_path=plan.destination,
        )
        self._append_item(
            summary,
            job=job,
            depot=depot,
            status=ActivityStatus.FAILED,
            reason=type(exc).__name__,
            source_path=plan.file.path,
            destination_path=plan.destination,
            summary_text=str(exc),
            context={**context, "error_type": type(exc).__name__},
        )
        summary.failed += 1
        summary.consecutive_timeouts = 0

    def job_exception(self, job: TransferJob, depot: Depot, exc: Exception):
        app_log.exception("transfer.worker", "Transfer job failed", exc=exc, trace_id=job.id, depot_id=depot.id)
        return self.activity.record_transfer_job_event(
            job=job,
            depot=depot,
            status=ActivityStatus.FAILED,
            reason=type(exc).__name__,
            summary=str(exc),
            context={
                "depot_id": depot.id,
                "depot_path": str(depot.path),
                "target_library_path": str(depot.policy.target_library_path),
                "media_type": depot.media_type.value,
                "error_type": type(exc).__name__,
            },
        )

    def completed(self, job: TransferJob, depot: Depot, summary: TransferSummary):
        return self.activity.record_transfer_job_event(
            job=job,
            depot=depot,
            status=summary.activity_status(),
            reason=summary.reason(),
            summary=summary.text(),
            context=summary.context(),
        )

    def locked(self, job: TransferJob, depot: Depot):
        app_log.warning("transfer.worker", "Depot lock unavailable", depot_id=depot.id, trace_id=job.id)
        return self.activity.record_transfer_job_event(
            job=job,
            depot=depot,
            status=ActivityStatus.FAILED,
            reason="depot_locked",
            summary=job.message,
            context={
                "depot_id": depot.id,
                "depot_path": str(depot.path),
                "target_library_path": str(depot.policy.target_library_path),
                "media_type": depot.media_type.value,
                "error_code": job.error_code.value,
            },
        )

    def cancelled(self, job: TransferJob, depot: Depot, summary: TransferSummary):
        return self.activity.record_transfer_job_event(
            job=job,
            depot=depot,
            action=ActivityAction.CANCEL,
            status=ActivityStatus.SUCCEEDED,
            reason="user_cancelled",
            summary=summary.text(cancelled=True),
            context={
                "depot_id": depot.id,
                "depot_path": str(depot.path),
                "target_library_path": str(depot.policy.target_library_path),
                "media_type": depot.media_type.value,
                "moved": summary.moved,
                "skipped": summary.skipped,
                "failed": summary.failed,
                "timed_out": summary.timed_out,
            },
        )

    def _append_item(
        self,
        summary: TransferSummary,
        *,
        job: TransferJob,
        depot: Depot,
        status: ActivityStatus,
        source_path,
        destination_path,
        summary_text: str,
        context: dict,
        reason: str | None = None,
    ) -> None:
        summary.activity_events.append(
            self.activity.record_transfer_item(
                area=_transfer_area(job),
                status=status,
                reason=reason,
                source_path=source_path,
                destination_path=destination_path,
                summary=summary_text,
                depot=depot,
                trace_id=job.id,
                context=context,
            )
        )


class TransferRun:
    def __init__(self, *, store, locks, activity, extensions, now=None, move_files=None):
        self.store = store
        self.locks = locks
        self.activity = activity
        self.extensions = extensions
        self.now = now or (lambda: datetime.now().astimezone())
        self.move_files = move_files or move_with_replace
        self.events = TransferEventLog(activity)

    def execute(self, job: TransferJob, depot: Depot, *, transfer_rule: TransferRule | None = None) -> TransferExecutionResult:
        self._start_job(job, depot)
        lease = self.locks.acquire(depot, blocking=False)
        if not lease:
            return self._fail_locked(job, depot)
        summary = TransferSummary()
        try:
            try:
                files, missing_scopes = self._transfer_files(job, depot)
                for missing_scope in missing_scopes:
                    self.events.missing_scope(summary, job=job, depot=depot, missing_scope=missing_scope)
                if not files and not missing_scopes:
                    summary.skipped = 1
                plans = self.build_plans(files, depot, transfer_rule=transfer_rule)
                plan_blocks = prepare_replace_roots(depot, plans)
                for plan in plans:
                    if self._cancellation_requested(job):
                        return self._cancel_running_job(job, depot, summary)
                    step_result = self._execute_transfer_plan(job, depot, plan, plan_blocks, transfer_rule, summary)
                    if isinstance(step_result, TransferExecutionResult):
                        return step_result
                    if step_result:
                        break
                    if self._cancellation_requested(job):
                        return self._cancel_running_job(job, depot, summary)
            except Exception as exc:
                return self._fail_job_exception(job, depot, exc)
            return self._complete_job(job, depot, summary)
        finally:
            lease.release()

    def _start_job(self, job: TransferJob, depot: Depot) -> None:
        job.status = TransferStatus.RUNNING
        job.started_at = self.now()
        self.store.save_transfer_job(job)
        self.events.started(job, depot)

    def build_plans(
        self,
        files: list[DiskFileEntry],
        depot: Depot,
        *,
        transfer_rule: TransferRule | None,
    ) -> list[TransferPlan]:
        engine = TransferRuleEngine()
        return [
            build_plan(file, depot, transfer_rule=transfer_rule, engine=engine)
            for file in files
        ]

    def _execute_transfer_plan(
        self,
        job: TransferJob,
        depot: Depot,
        plan: TransferPlan,
        plan_blocks: dict[str, TransferPlanBlock],
        transfer_rule: TransferRule | None,
        summary: TransferSummary,
    ) -> TransferExecutionResult | bool:
        file = plan.file
        destination = plan.destination
        context = plan_context(job, depot, plan, transfer_rule)
        plan_block = plan_blocks.get(plan_key(plan))
        if plan_block is not None:
            self.events.plan_block(summary, job=job, depot=depot, plan=plan, plan_block=plan_block, context=context)
            return False
        try:
            move_result = self.move_files(
                file.path,
                destination,
                cleanup_root=depot.path,
                sidecar_extensions=frozenset(),
                cleanup_stop_root=plan.cleanup_stop_root,
            )
        except Exception as exc:
            self.events.plan_exception(summary, job=job, depot=depot, plan=plan, context=context, exc=exc)
            return False
        context = {**context, **move_result.context()}
        if plan.destination_preexisting_size is not None and "overwritten_size" not in context:
            context["overwritten_size"] = plan.destination_preexisting_size
        if move_result.status == StorageMoveStatus.SUCCEEDED:
            self.events.plan_success(summary, job=job, depot=depot, plan=plan, context=context)
            if self._cancellation_requested(job):
                return self._cancel_running_job(job, depot, summary)
            return False
        if move_result.status == StorageMoveStatus.TIMEOUT:
            self.events.plan_timeout(summary, job=job, depot=depot, plan=plan, move_result=move_result, context=context)
            if summary.consecutive_timeouts >= CONSECUTIVE_TIMEOUT_LIMIT:
                summary.failed += 1
                summary.hard_timeout_stop = True
                return True
            if self._cancellation_requested(job):
                return self._cancel_running_job(job, depot, summary)
            return False
        self.events.plan_failure(summary, job=job, depot=depot, plan=plan, move_result=move_result, context=context)
        if move_result.status == StorageMoveStatus.AMBIGUOUS:
            summary.hard_timeout_stop = True
            return True
        return False

    def _fail_job_exception(self, job: TransferJob, depot: Depot, exc: Exception) -> TransferExecutionResult:
        job.status = TransferStatus.FAILED
        job.error_code = TransferErrorCode.MOVE_FAILED
        job.message = str(exc)
        job.finished_at = self.now()
        self.store.save_transfer_job(job)
        entry = self.events.job_exception(job, depot, exc)
        return TransferExecutionResult(job=job, failed=1, activity_events=[entry])

    def _complete_job(self, job: TransferJob, depot: Depot, summary: TransferSummary) -> TransferExecutionResult:
        job.status = summary.status()
        job.error_code = summary.error_code()
        job.message = summary.job_message()
        job.finished_at = self.now()
        self.store.save_transfer_job(job)
        completed = self.events.completed(job, depot, summary)
        return TransferExecutionResult(
            job=job,
            moved=summary.moved,
            skipped=summary.skipped,
            failed=summary.failed,
            timed_out=summary.timed_out,
            hard_timeout_stop=summary.hard_timeout_stop,
            activity_events=[*summary.activity_events, completed],
        )

    def _fail_locked(self, job: TransferJob, depot: Depot) -> TransferExecutionResult:
        job.status = TransferStatus.FAILED
        job.error_code = TransferErrorCode.DEPOT_LOCKED
        job.message = "Depot lock is unavailable"
        job.finished_at = self.now()
        self.store.save_transfer_job(job)
        entry = self.events.locked(job, depot)
        return TransferExecutionResult(job=job, failed=1, activity_events=[entry])

    def _cancellation_requested(self, job: TransferJob) -> bool:
        current = self.store.get_transfer_job(job.id)
        return current is not None and current.status == TransferStatus.CANCELLING

    def _cancel_running_job(
        self,
        job: TransferJob,
        depot: Depot,
        summary: TransferSummary,
    ) -> TransferExecutionResult:
        job.status = TransferStatus.CANCELLED
        job.error_code = None
        job.message = summary.job_message(cancelled=True)
        job.finished_at = self.now()
        self.store.save_transfer_job(job)
        cancellation_entry = self.events.cancelled(job, depot, summary)
        return TransferExecutionResult(
            job=job,
            moved=summary.moved,
            skipped=summary.skipped,
            failed=summary.failed,
            timed_out=summary.timed_out,
            activity_events=[*summary.activity_events, cancellation_entry],
        )

    def _transfer_files(self, job: TransferJob, depot: Depot) -> tuple[list[DiskFileEntry], list[CandidateScope]]:
        scopes = job.metadata.get("candidate_scope") if isinstance(job.metadata, dict) else None
        if isinstance(scopes, list) and scopes:
            book = CandidateBook(depot, self.extensions)
            candidates = []
            missing: list[CandidateScope] = []
            for raw_scope in scopes:
                scope = CandidateScope.from_payload(raw_scope) or CandidateScope(id=str(raw_scope))
                candidate = book.from_scope(scope)
                if candidate is None:
                    missing.append(scope)
                    continue
                candidates.append(candidate)
            return expand_depot_candidate_files(candidates), missing
        return expand_depot_candidate_files(scan_depot_candidates(depot, self.extensions)), []


def _transfer_area(job: TransferJob) -> ActivityArea:
    return ActivityArea.SCHEDULED_TRANSFER if job.requested_by == "schedule" else ActivityArea.MANUAL_TRANSFER
