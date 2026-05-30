from __future__ import annotations

from collections.abc import Mapping

from app.api.http.present.inventory import present_file_detail
from app.api.http.schemas.config import OrganizePolicy
from app.api.http.schemas.organize import (
    BulkSessionItemResult,
    CandidateMatch,
    CandidatePreview,
    ConflictReview,
    IdentifySearchResults,
    IdentifySearchResult,
    OrganizeResult,
    OrganizeSession,
    PlanItem,
    PlanItemResult,
    ReviewAcceptance,
    SourceActionOutcome,
    SourceCandidate,
    SourceFile,
    SourceFileDetail,
)


def present_session(session) -> OrganizeSession:
    return OrganizeSession(
        id=session.id,
        kind=session.kind,
        path=session.path,
        media_type=session.media_type,
        policy=OrganizePolicy(
            target_depot_id=_policy_value(session.policy, "target_depot_id"),
            organize_rule_id=_policy_value(session.policy, "organize_rule_id"),
        ),
        state=session.state,
        created_at=session.created_at,
        last_active_at=session.last_active_at,
        expires_at=session.expires_at,
        idle_timeout_seconds=session.idle_timeout_seconds,
        review_candidates=[present_source_review_candidate(candidate) for candidate in session.review_candidates],
        last_source_action_outcome=_present_source_action_outcome(session.last_source_action_outcome),
    )


def present_source_review_candidate(candidate) -> SourceCandidate:
    return SourceCandidate(
        id=candidate.id,
        media_type=candidate.media_type,
        source_root=candidate.source_root,
        source_path=candidate.source_path,
        display_name=candidate.display_name,
        structure=candidate.structure,
        kind=candidate.kind,
        status=candidate.status,
        selection_decision=candidate.selection_decision,
        file_count=candidate.file_count,
        active_file_count=candidate.active_file_count,
        total_size=candidate.total_size,
        active_total_size=candidate.active_total_size,
        modified_time=candidate.modified_time,
        files=[_present_source_file(file) for file in candidate.files],
        match=_present_candidate_match(candidate.match),
        plan_items=[_present_plan_item(item) for item in candidate.plan_items],
        conflict_reviews=[_present_conflict_review(review) for review in candidate.conflict_reviews],
        warnings=list(candidate.warnings),
    )


def present_source_file_detail(detail: Mapping[str, object]) -> SourceFileDetail:
    return SourceFileDetail(
        path=detail["path"],
        exists=detail["exists"],
        file_type=detail["file_type"],
        size_bytes=detail.get("size_bytes"),
        created_time=detail.get("created_time"),
        modified_time=detail.get("modified_time"),
        classification=detail["classification"],
        source_candidate_id=detail["source_candidate_id"],
        source_candidate_display_name=detail["source_candidate_display_name"],
        source_candidate_kind=detail.get("source_candidate_kind"),
        source_candidate_status=detail.get("source_candidate_status"),
        source_candidate_path=detail.get("source_candidate_path"),
        source_root=detail.get("source_root"),
        file_count=detail.get("file_count"),
        total_size=detail.get("total_size"),
        source_file_id=detail["source_file_id"],
        relative_path=detail["relative_path"],
        blocked_reason=detail.get("blocked_reason"),
    )


def present_bulk_session_item(item) -> BulkSessionItemResult:
    return BulkSessionItemResult(
        origin_id=item.origin_id,
        status=item.status,
        session_id=item.session_id,
        message=item.message,
        code=item.code,
        details=dict(item.details) if item.details is not None else None,
    )


def present_tmdb_search_response(page) -> IdentifySearchResults:
    return IdentifySearchResults(
        results=[
            IdentifySearchResult(
                tmdb_id=item.tmdb_id,
                media_type=item.media_type,
                title=item.title,
                original_title=item.original_title,
                year=item.year,
                overview=item.overview,
                poster_url=item.poster_url,
                vote_average=item.vote_average,
                popularity=item.popularity,
                origin_country=list(item.origin_country),
                directors=list(item.directors),
                cast=list(item.cast),
                confidence=item.confidence,
                score=item.score,
                reason=item.reason,
            )
            for item in page.results
        ],
        page=page.page,
        total_pages=page.total_pages,
        total_results=page.total_results,
    )


def present_session_execution_result(session_id: str, result, source_candidate_by_plan: dict[str, str | None]) -> OrganizeResult:
    return OrganizeResult(
        session_id=session_id,
        moved=result.moved,
        skipped=result.skipped,
        failed=result.failed,
        results=[
            PlanItemResult(
                plan_item_id=item.candidate_id,
                source_candidate_id=source_candidate_by_plan.get(item.candidate_id),
                status=item.status,
                source_path=item.source_path,
                destination_path=item.destination_path,
                message=item.message,
            )
            for item in result.results
        ],
    )


def _present_source_file(file) -> SourceFile:
    return SourceFile(
        id=file.id,
        path=file.path,
        relative_path=file.relative_path,
        extension=file.extension,
        classification=file.classification,
        status=file.status,
        size_bytes=file.size_bytes,
        modified_time=file.modified_time,
        planned_item_ids=list(file.planned_item_ids),
        plan_status=file.plan_status,
    )


def _present_candidate_match(match) -> CandidateMatch | None:
    if match is None:
        return None
    return CandidateMatch(
        source_candidate_id=match.source_candidate_id,
        confidence=match.confidence,
        metadata=dict(match.metadata) if match.metadata is not None else None,
        metadata_source=match.metadata_source,
        manual_override_tmdb_id=match.manual_override_tmdb_id,
        evidence=dict(match.evidence),
        acceptance=_present_acceptance(match.acceptance),
    )


def _present_plan_item(item) -> PlanItem:
    return PlanItem(
        id=item.id,
        source_candidate_id=item.source_candidate_id,
        source_file_id=item.source_file_id,
        source_path=item.source_path,
        source_size=item.source_size,
        source_mtime=item.source_mtime,
        confidence=item.confidence,
        metadata=dict(item.metadata) if item.metadata is not None else None,
        metadata_source=item.metadata_source,
        manual_override_tmdb_id=item.manual_override_tmdb_id,
        evidence=dict(item.evidence),
        preview=CandidatePreview(
            preview_bucket=item.preview.preview_bucket,
            matched_category=item.preview.matched_category,
            proposed_relative_path=item.preview.proposed_relative_path,
            render_warnings=list(item.preview.render_warnings),
        ),
        user_decision=item.user_decision,
        acceptance=_present_acceptance(item.acceptance),
    )


def _present_acceptance(acceptance) -> ReviewAcceptance:
    return ReviewAcceptance(
        can_accept=acceptance.can_accept,
        blockers=list(acceptance.blockers),
    )


def _present_conflict_review(review) -> ConflictReview:
    return ConflictReview(
        identity_key=review.identity_key,
        kind=review.kind,
        status=review.status,
        display_path=review.display_path,
        root_relative_path=review.root_relative_path,
        plan_item_ids=list(review.plan_item_ids),
        source_candidate_ids=list(review.source_candidate_ids),
        accepted_source_candidate_ids=list(review.accepted_source_candidate_ids),
        action_required=review.action_required,
        conflict=review.conflict,
        conflict_reason=review.conflict_reason,
        existing=review.existing,
        action=review.action,
        action_source_candidate_id=review.action_source_candidate_id,
        replace_intent=review.replace_intent,
        source_tag=review.source_tag,
    )


def _present_source_action_outcome(outcome: object | None) -> SourceActionOutcome | None:
    if outcome is None:
        return None
    return SourceActionOutcome(
        operation=_outcome_value(outcome, "operation"),
        status=_outcome_value(outcome, "status"),
        scope=_outcome_value(outcome, "scope"),
        source_candidate_id=_outcome_value(outcome, "source_candidate_id"),
        source_file_id=_outcome_value(outcome, "source_file_id"),
        old_source_file_id=_outcome_value(outcome, "old_source_file_id"),
        new_source_file_id=_outcome_value(outcome, "new_source_file_id"),
        message=_outcome_value(outcome, "message"),
        file_count=_outcome_value(outcome, "file_count"),
        total_size=_outcome_value(outcome, "total_size"),
        old_path=_outcome_value(outcome, "old_path"),
        new_path=_outcome_value(outcome, "new_path"),
        exists_after=_outcome_value(outcome, "exists_after"),
        exists_after_old=_outcome_value(outcome, "exists_after_old"),
        exists_after_new=_outcome_value(outcome, "exists_after_new"),
        blocked_reason=_outcome_value(outcome, "blocked_reason"),
    )


def _policy_value(policy, key: str) -> str | None:
    if isinstance(policy, Mapping):
        return policy.get(key)
    return getattr(policy, key)


def _outcome_value(outcome: object, key: str) -> object:
    if isinstance(outcome, Mapping):
        return outcome.get(key)
    return getattr(outcome, key)
