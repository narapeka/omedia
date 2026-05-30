from __future__ import annotations

from app.api.http.schemas.depot import (
    DepotCandidateActionOutcome,
    DepotCandidateFile,
    DepotCandidateGroup,
    DepotCandidateMutationResult,
    DepotCandidate,
    DepotDetail,
    Depot,
    DepotSummary,
)
from app.api.http.schemas.transfer import TransferPolicy
from app.api.http.present.inventory import present_file_detail
from app.api.http.present.transfer import present_transfer_job
from app.domain.transfer import TransferStatus


def present_depot(depot) -> Depot:
    return Depot(
        id=depot.id,
        name=depot.name,
        path=depot.path,
        media_type=depot.media_type,
        enabled=depot.enabled,
        resolve_mode=depot.resolve_mode.value,
        policy=TransferPolicy(
            target_library_path=depot.policy.target_library_path,
            trigger=depot.policy.trigger.value,
            transfer_rule_id=depot.policy.transfer_rule_id,
            schedule=depot.policy.schedule,
        ),
    )


def present_depot_summary(depot, jobs) -> DepotSummary:
    depot_model = present_depot(depot)
    last_success = next((job for job in jobs if job.status == TransferStatus.SUCCEEDED), None)
    last_failure = next((job for job in jobs if job.status == TransferStatus.FAILED), None)
    return DepotSummary(
        id=depot_model.id,
        name=depot_model.name,
        path=depot_model.path,
        media_type=depot_model.media_type,
        enabled=depot_model.enabled,
        resolve_mode=depot_model.resolve_mode,
        policy=depot_model.policy,
        last_successful_transfer=present_transfer_job(last_success) if last_success else None,
        last_failed_transfer=present_transfer_job(last_failure) if last_failure else None,
        recent_transfers=[present_transfer_job(job) for job in jobs[:5]],
    )


def present_depot_detail(depot, detail, jobs) -> DepotDetail:
    summary = present_depot_summary(depot, jobs)
    return DepotDetail(
        id=summary.id,
        name=summary.name,
        path=summary.path,
        media_type=summary.media_type,
        enabled=summary.enabled,
        resolve_mode=summary.resolve_mode,
        policy=summary.policy,
        pending_count=sum(candidate.file_count for candidate in detail.candidates),
        last_successful_transfer=summary.last_successful_transfer,
        last_failed_transfer=summary.last_failed_transfer,
        recent_transfers=summary.recent_transfers,
        candidates=[present_candidate(candidate) for candidate in detail.candidates],
    )


def present_candidate(candidate) -> DepotCandidate:
    return DepotCandidate(
        id=candidate.id,
        kind=candidate.kind,
        path=candidate.path,
        relative_path=candidate.relative_path,
        display_name=candidate.display_name,
        size_bytes=candidate.size_bytes,
        modified_time=candidate.modified_time,
        file_count=candidate.file_count,
        media_count=candidate.media_count,
        group=present_candidate_group(candidate.group),
        media_relative_path=candidate.media_relative_path,
        path_split_confidence=candidate.path_split_confidence,
        files=[present_candidate_file(file) for file in candidate.files],
        tree=candidate.tree,
        blocked_reason=candidate.blocked_reason,
    )


def present_candidate_file(file) -> DepotCandidateFile:
    return DepotCandidateFile(
        id=file.id,
        path=file.path,
        relative_path=file.relative_path,
        candidate_relative_path=file.candidate_relative_path,
        display_name=file.display_name,
        size_bytes=file.size_bytes,
        modified_time=file.modified_time,
        extension=file.extension,
        is_media=file.is_media,
        blocked_reason=file.blocked_reason,
    )


def present_candidate_group(group) -> DepotCandidateGroup | None:
    if group is None:
        return None
    return DepotCandidateGroup(
        key=group.key,
        organize_prefix=group.organize_prefix,
        display_name=group.display_name,
    )


def present_mutation_response(result) -> DepotCandidateMutationResult:
    return DepotCandidateMutationResult(
        outcome=present_action_outcome(result.outcome),
    )


def present_action_outcome(outcome) -> DepotCandidateActionOutcome:
    return DepotCandidateActionOutcome(
        action=outcome.action,
        scope=outcome.scope,
        status=outcome.status,
        depot_id=outcome.depot_id,
        candidate_id=outcome.candidate_id,
        old_candidate_id=outcome.old_candidate_id,
        new_candidate_id=outcome.new_candidate_id,
        file_id=outcome.file_id,
        old_file_id=outcome.old_file_id,
        new_file_id=outcome.new_file_id,
        old_path=outcome.old_path,
        new_path=outcome.new_path,
        affected_file_count=outcome.affected_file_count,
        total_size_bytes=outcome.total_size_bytes,
        message=outcome.message,
        blocked_reason=outcome.blocked_reason,
    )
