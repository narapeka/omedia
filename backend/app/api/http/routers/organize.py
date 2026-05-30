from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.http.deps import Organize
from app.api.http.present.organize import (
    present_bulk_session_item,
    present_file_detail,
    present_session,
    present_session_execution_result,
    present_source_file_detail,
    present_source_review_candidate,
)
from app.api.http.schemas.common import DEFAULT_API_RESPONSES
from app.api.http.schemas.organize import (
    CandidateDecisionRequest,
    OrganizeBulkSessionCreateRequest,
    OrganizeBulkSessionCreateResult,
    OrganizeRequest,
    OrganizeResult,
    OrganizeSession,
    ConflictReviewActionRequest,
    RenameRequest,
    SourceCandidateDetail,
    SourceFileDetail,
)

router = APIRouter(prefix="/organize", tags=["organize"], responses=DEFAULT_API_RESPONSES)


@router.get("/sessions", response_model=list[OrganizeSession])
def list_organize_sessions(organize: Organize) -> list[OrganizeSession]:
    return [present_session(organize.views.session(session)) for session in organize.active_sessions()]


@router.get("/sessions/{session_id}", response_model=OrganizeSession)
def organize_session(session_id: str, organize: Organize) -> OrganizeSession:
    return present_session(organize.views.by_id(session_id))


@router.post("/sessions", response_model=OrganizeSession)
def create_organize_session(payload: OrganizeRequest, organize: Organize) -> OrganizeSession:
    session = organize.create_session(
        origin_id=payload.origin_id,
        source_path=payload.source_path,
        media_type=payload.media_type,
        target_depot_id=payload.policy.target_depot_id if payload.policy else None,
        organize_rule_id=payload.policy.organize_rule_id if payload.policy else None,
    )
    return present_session(organize.views.session(session))


@router.post("/sessions/bulk", response_model=OrganizeBulkSessionCreateResult)
def create_organize_sessions_bulk(payload: OrganizeBulkSessionCreateRequest, organize: Organize) -> OrganizeBulkSessionCreateResult:
    result = organize.create_sessions_bulk(payload.origin_ids)
    return OrganizeBulkSessionCreateResult(
        sessions=[present_session(organize.views.session(session)) for session in result.sessions],
        results=[present_bulk_session_item(item) for item in result.results],
    )


@router.post("/sessions/{session_id}/scan", response_model=OrganizeSession)
def scan_organize_session(session_id: str, organize: Organize) -> OrganizeSession:
    return present_session(organize.views.session(organize.restart_scan(session_id)))


@router.delete("/sessions/{session_id}", response_model=OrganizeSession)
def cancel_organize_session(session_id: str, organize: Organize) -> OrganizeSession:
    return present_session(organize.views.session(organize.cancel(session_id)))


@router.get("/sessions/{session_id}/candidates/{candidate_id}/detail", response_model=SourceCandidateDetail)
def organize_candidate_detail(
    session_id: str,
    candidate_id: str,
    organize: Organize,
) -> SourceCandidateDetail:
    detail = organize.source_candidate_detail(session_id, candidate_id)
    candidate = present_source_review_candidate(organize.views.source_candidate(session_id, candidate_id))
    return SourceCandidateDetail(candidate=candidate, detail=present_file_detail(detail))


@router.get("/sessions/{session_id}/candidates/{candidate_id}/files/{file_id}/detail", response_model=SourceFileDetail)
def organize_candidate_file_detail(
    session_id: str,
    candidate_id: str,
    file_id: str,
    organize: Organize,
) -> SourceFileDetail:
    detail = organize.source_file_detail(session_id, candidate_id, file_id)
    return present_source_file_detail(detail)


@router.delete("/sessions/{session_id}/candidates/{candidate_id}/files/{file_id}", response_model=OrganizeSession)
def delete_organize_candidate_file(
    session_id: str,
    candidate_id: str,
    file_id: str,
    organize: Organize,
) -> OrganizeSession:
    return present_session(organize.views.session(organize.delete_source_file(session_id, candidate_id, file_id)))


@router.put("/sessions/{session_id}/candidates/{candidate_id}/files/{file_id}/rename", response_model=OrganizeSession)
def rename_organize_candidate_file(
    session_id: str,
    candidate_id: str,
    file_id: str,
    payload: RenameRequest,
    organize: Organize,
) -> OrganizeSession:
    return present_session(organize.views.session(organize.rename_source_file(session_id, candidate_id, file_id, payload.new_name)))


@router.delete("/sessions/{session_id}/candidates/{candidate_id}", response_model=OrganizeSession)
def delete_organize_candidate(
    session_id: str,
    candidate_id: str,
    organize: Organize,
) -> OrganizeSession:
    return present_session(organize.views.session(organize.delete_source_candidate(session_id, candidate_id)))


@router.put("/sessions/{session_id}/candidates/{candidate_id}/rename", response_model=OrganizeSession)
def rename_organize_candidate(
    session_id: str,
    candidate_id: str,
    payload: RenameRequest,
    organize: Organize,
) -> OrganizeSession:
    return present_session(organize.views.session(organize.rename_source_candidate(session_id, candidate_id, payload.new_name)))


@router.put("/sessions/{session_id}/plan-items/{plan_item_id}/decision", status_code=status.HTTP_204_NO_CONTENT)
def set_organize_plan_item_decision(
    session_id: str,
    plan_item_id: str,
    payload: CandidateDecisionRequest,
    organize: Organize,
) -> Response:
    organize.set_plan_item_decision(session_id, plan_item_id, payload.decision)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/sessions/{session_id}/candidates/{candidate_id}/decision", status_code=status.HTTP_204_NO_CONTENT)
def set_organize_candidate_decision(
    session_id: str,
    candidate_id: str,
    payload: CandidateDecisionRequest,
    organize: Organize,
) -> Response:
    organize.set_source_candidate_decision(session_id, candidate_id, payload.decision)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/{session_id}/conflict-reviews/action", response_model=OrganizeSession)
def apply_conflict_review_action(
    session_id: str,
    payload: ConflictReviewActionRequest,
    organize: Organize,
) -> OrganizeSession:
    updated = organize.apply_conflict_review_action(
        session_id,
        identity_key=payload.identity_key,
        source_candidate_id=payload.source_candidate_id,
        action=payload.action,
        tag_override=payload.tag_override,
    )
    return present_session(organize.views.session(updated))


@router.post("/sessions/{session_id}/execute", response_model=OrganizeResult)
def execute_organize_session(session_id: str, organize: Organize) -> OrganizeResult:
    execution = organize.execute_session(session_id)
    return present_session_execution_result(session_id, execution.result, execution.source_candidate_by_plan)
