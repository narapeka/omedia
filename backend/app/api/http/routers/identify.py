from __future__ import annotations

from fastapi import APIRouter

from app.api.http.deps import Organize
from app.api.http.present.organize import present_session, present_tmdb_search_response
from app.api.http.schemas.common import DEFAULT_API_RESPONSES
from app.api.http.schemas.organize import (
    OrganizeSession,
    IdentifySearchRequest,
    IdentifySearchResults,
    IdentityOverrideRequest,
)

router = APIRouter(prefix="/identify", tags=["identify"], responses=DEFAULT_API_RESPONSES)


@router.post("/sessions/{session_id}", response_model=OrganizeSession)
def identify_session(session_id: str, organize: Organize) -> OrganizeSession:
    return present_session(organize.views.session(organize.identify_session(session_id)))


@router.post("/sessions/{session_id}/search", response_model=IdentifySearchResults)
def search_identify_session(
    session_id: str,
    payload: IdentifySearchRequest,
    organize: Organize,
) -> IdentifySearchResults:
    page = organize.search_tmdb(
        session_id,
        source_candidate_id=payload.source_candidate_id,
        query=payload.query,
        year=payload.year,
        language=payload.language,
        page=payload.page,
    )
    return present_tmdb_search_response(page)


@router.put("/sessions/{session_id}/candidates/{candidate_id}/override", response_model=OrganizeSession)
def apply_identify_candidate_override(
    session_id: str,
    candidate_id: str,
    payload: IdentityOverrideRequest,
    organize: Organize,
) -> OrganizeSession:
    updated = organize.apply_source_candidate_tmdb_override(session_id, candidate_id, tmdb_id=payload.tmdb_id)
    return present_session(organize.views.session(updated))
