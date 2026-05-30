from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.http.deps import Config, Depot
from app.api.http.present.depot import (
    present_candidate,
    present_candidate_file,
    present_depot,
    present_depot_detail,
    present_depot_summary,
    present_file_detail,
    present_mutation_response,
)
from app.api.http.schemas.common import DEFAULT_API_RESPONSES
from app.api.http.schemas.depot import (
    Depot as DepotModel,
    DepotDraft,
    DepotCandidateDetail,
    DepotCandidateFileDetail,
    DepotCandidateMutationResult,
    DepotDetail,
    DepotSummary,
    ReturnResult,
    RenameRequest,
    ReturnRequest,
)
from app.domain.depot import Depot as DomainDepot, ResolveMode, TransferPolicy as DomainTransferPolicy
from app.domain.ids import new_object_id
from app.domain.media import MediaType
from app.domain.transfer import TransferTrigger

router = APIRouter(prefix="/depots", tags=["depots"], responses=DEFAULT_API_RESPONSES)


@router.get("", response_model=list[DepotSummary])
def list_depots(config: Config) -> list[DepotSummary]:
    return [
        present_depot_summary(depot, config.transfer_history(depot))
        for depot in config.list_depots()
    ]


@router.post("", response_model=DepotModel)
def create_depot(payload: DepotDraft, config: Config) -> DepotModel:
    depot = _depot_from_schema(payload, depot_id=new_object_id("depot"))
    return present_depot(config.save_depot(depot))


@router.put("/{depot_id}", response_model=DepotModel)
def save_depot(depot_id: str, payload: DepotDraft, config: Config) -> DepotModel:
    depot = _depot_from_schema(payload, depot_id=depot_id)
    return present_depot(config.save_depot(depot))


@router.delete("/{depot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_depot(depot_id: str, config: Config) -> Response:
    config.delete_depot(depot_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{depot_id}", response_model=DepotDetail)
def depot_detail(depot_id: str, config: Config, depots: Depot) -> DepotDetail:
    depot = config.get_depot(depot_id)
    return present_depot_detail(
        depot,
        depots.depot_detail(depot),
        depots.transfer_history(depot),
    )


@router.post("/{depot_id}/return", response_model=ReturnResult)
def return_depot_items(depot_id: str, payload: ReturnRequest, config: Config, depots: Depot) -> ReturnResult:
    depot = config.get_depot(depot_id)
    activity_events = depots.return_items(
        depot,
        payload.relative_paths,
        payload.destination_root,
        candidate_ids=payload.candidate_ids,
    )
    return ReturnResult(
        activity_events=[event.id for event in activity_events],
    )


@router.get("/{depot_id}/candidates/{candidate_id}/detail", response_model=DepotCandidateDetail)
def depot_candidate_detail(
    depot_id: str,
    candidate_id: str,
    config: Config,
    depots: Depot,
) -> DepotCandidateDetail:
    depot = config.get_depot(depot_id)
    result = depots.candidate_detail(depot, candidate_id)
    return DepotCandidateDetail(
        candidate=present_candidate(result.candidate),
        detail=present_file_detail(result.detail),
    )


@router.put("/{depot_id}/candidates/{candidate_id}/rename", response_model=DepotCandidateMutationResult)
def rename_depot_candidate(
    depot_id: str,
    candidate_id: str,
    payload: RenameRequest,
    config: Config,
    depots: Depot,
) -> DepotCandidateMutationResult:
    depot = config.get_depot(depot_id)
    result = depots.candidate_rename(depot, candidate_id, payload.new_name)
    return present_mutation_response(result)


@router.delete("/{depot_id}/candidates/{candidate_id}", response_model=DepotCandidateMutationResult)
def delete_depot_candidate(
    depot_id: str,
    candidate_id: str,
    config: Config,
    depots: Depot,
) -> DepotCandidateMutationResult:
    depot = config.get_depot(depot_id)
    result = depots.candidate_delete(depot, candidate_id)
    return present_mutation_response(result)


@router.get("/{depot_id}/candidates/{candidate_id}/files/{file_id}/detail", response_model=DepotCandidateFileDetail)
def depot_candidate_file_detail(
    depot_id: str,
    candidate_id: str,
    file_id: str,
    config: Config,
    depots: Depot,
) -> DepotCandidateFileDetail:
    depot = config.get_depot(depot_id)
    result = depots.candidate_file_detail(depot, candidate_id, file_id)
    return DepotCandidateFileDetail(
        candidate=present_candidate(result.candidate),
        file=present_candidate_file(result.file),
        detail=present_file_detail(result.detail),
    )


@router.put("/{depot_id}/candidates/{candidate_id}/files/{file_id}/rename", response_model=DepotCandidateMutationResult)
def rename_depot_candidate_file(
    depot_id: str,
    candidate_id: str,
    file_id: str,
    payload: RenameRequest,
    config: Config,
    depots: Depot,
) -> DepotCandidateMutationResult:
    depot = config.get_depot(depot_id)
    result = depots.candidate_file_rename(depot, candidate_id, file_id, payload.new_name)
    return present_mutation_response(result)


@router.delete("/{depot_id}/candidates/{candidate_id}/files/{file_id}", response_model=DepotCandidateMutationResult)
def delete_depot_candidate_file(
    depot_id: str,
    candidate_id: str,
    file_id: str,
    config: Config,
    depots: Depot,
) -> DepotCandidateMutationResult:
    depot = config.get_depot(depot_id)
    result = depots.candidate_file_delete(depot, candidate_id, file_id)
    return present_mutation_response(result)


def _depot_from_schema(payload: DepotDraft, *, depot_id: str) -> DomainDepot:
    media_type = MediaType(payload.media_type)
    return DomainDepot(
        id=depot_id,
        name=payload.name.strip(),
        path=payload.path,
        media_type=media_type,
        enabled=payload.enabled,
        resolve_mode=ResolveMode.FULL if media_type == MediaType.MOVIE else ResolveMode(payload.resolve_mode),
        policy=DomainTransferPolicy(
            target_library_path=payload.policy.target_library_path,
            trigger=TransferTrigger(payload.policy.trigger),
            transfer_rule_id=payload.policy.transfer_rule_id,
            schedule=payload.policy.schedule,
        ),
    )
