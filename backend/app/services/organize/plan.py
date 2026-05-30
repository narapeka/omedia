from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from app.domain.depot import Depot
from app.domain.media import MediaType
from app.domain.media import MediaCandidate, MediaExtensionPolicy
from app.domain.organize import OrganizePlanItem
from app.domain.rule import OrganizeRule
from app.domain.tv import TVEpisodeFile
from app.engines.plan.movie.evidence import movie_plan_part_token, movie_plan_tag_suffix
from app.engines.plan.tv.evidence import (
    set_tv_episode_title_evidence,
    tv_episode_from_candidate,
    tv_episode_plan_tag_suffix,
)
from app.engines.plan.tv.catalog import episode_title_from_metadata
from app.services.identify.candidate import CandidateMatch, match_result_from_candidate, optional_int
from app.services.identify.preview import Preview, build_preview_from_metadata
from app.services.organize.session import (
    OrganizeSession,
    OrganizeSessionError,
    SourceCandidateStatus,
    SourceFileStatus,
)
from app.services.organize.candidate import file_state, find_media_candidate, source_state
from app.services.organize.review import sort_plan_items
from app.services.organize.review import apply_existing_tag_overrides, apply_conflict_review_defaults


def active_media_candidate(
    task: OrganizeSession,
    candidate: MediaCandidate,
    extensions: MediaExtensionPolicy,
) -> MediaCandidate | None:
    candidate_state = source_state(task, candidate.id)
    if candidate_state.status != SourceCandidateStatus.ACTIVE:
        return None
    files = [
        file
        for file in candidate.files
        if file_state(task, candidate.id, file).status == SourceFileStatus.ACTIVE
    ]
    if not any(file.extension.lower() in extensions.video for file in files):
        candidate_state.status = SourceCandidateStatus.UNAVAILABLE
        return None
    return replace(candidate, files=files)

def items_for_candidate(
    task: OrganizeSession,
    media_candidate: MediaCandidate,
    match: CandidateMatch,
    *,
    extensions: MediaExtensionPolicy,
    organize_rule: OrganizeRule | None,
    tv_episode_planner,
) -> list[OrganizePlanItem]:
    active_candidate = active_media_candidate(task, media_candidate, extensions)
    if active_candidate is None:
        return []
    return Preview.for_candidate(
        media_candidate=active_candidate,
        source_root=task.path,
        match_result=match_result_from_candidate(match, media_type=task.media_type),
        policy=task.policy,
        organize_rule=organize_rule,
        extensions=extensions,
        tv_episode_planner=tv_episode_planner,
    )

def rebuild_source_candidate(
    task: OrganizeSession,
    source_candidate_id: str,
    *,
    extensions: MediaExtensionPolicy,
    organize_rule: OrganizeRule | None,
    tv_episode_planner,
    target_depot: Depot | None = None,
) -> None:
    preserved_decisions = {item.source_file_id: item.user_decision for item in task.plan_items if item.source_candidate_id == source_candidate_id}
    task.plan_items = [item for item in task.plan_items if item.source_candidate_id != source_candidate_id]
    media_candidate = find_media_candidate(task, source_candidate_id)
    match = task.candidate_matches.get(source_candidate_id)
    if match is None:
        return
    rebuilt = items_for_candidate(
        task,
        media_candidate,
        match,
        extensions=extensions,
        organize_rule=organize_rule,
        tv_episode_planner=tv_episode_planner,
    )
    for item in rebuilt:
        item.user_decision = preserved_decisions.get(item.source_file_id)
    task.plan_items = sort_plan_items([*task.plan_items, *rebuilt])
    apply_existing_tag_overrides(task, source_candidate_id=source_candidate_id)
    apply_conflict_review_defaults(task, target_depot=target_depot)

def apply_match_to_item(
    task: OrganizeSession,
    item: OrganizePlanItem,
    match: CandidateMatch,
    *,
    organize_rule: OrganizeRule | None,
) -> None:
    item.metadata = dict(match.metadata or {})
    item.metadata_source = match.metadata_source
    item.manual_override_tmdb_id = match.manual_override_tmdb_id
    item.confidence = match.confidence
    tv_episode = tv_episode_from_candidate(item)
    tv_episode_title = _episode_title_for_plan_item(task, item, tv_episode)
    item.preview = build_preview_from_metadata(
        source_path=item.source_path,
        source_root=task.path,
        media_type=task.media_type,
        metadata=item.metadata,
        organize_rule=organize_rule,
        tv_episode_title=tv_episode_title,
        tv_episode=tv_episode,
        movie_part_token=_movie_part_token_from_plan_item(item) if task.media_type == MediaType.MOVIE else None,
        tag_suffix=_tag_suffix_from_plan_item(item),
    )
    _sync_tv_episode_title_evidence(item, tv_episode_title)
    item.evidence.setdefault("manual_override", {})["tmdb_id"] = match.manual_override_tmdb_id

def _episode_title_for_plan_item(
    task: OrganizeSession,
    item: OrganizePlanItem,
    tv_episode: TVEpisodeFile | None,
) -> str | None:
    if task.media_type != MediaType.TV or tv_episode is None:
        return None
    return episode_title_from_metadata(item.metadata, tv_episode.season_number, tv_episode.episode_number)

def _sync_tv_episode_title_evidence(item: OrganizePlanItem, title: str | None) -> None:
    set_tv_episode_title_evidence(item.evidence, title, "metadata" if title else "none")

def _movie_part_token_from_plan_item(item: OrganizePlanItem) -> str | None:
    return movie_plan_part_token(item.evidence)

def _tag_suffix_from_plan_item(item: OrganizePlanItem) -> str | None:
    return movie_plan_tag_suffix(item.evidence) or tv_episode_plan_tag_suffix(item.evidence)

def fallback_search_title(task: OrganizeSession, candidate: MediaCandidate | None) -> str | None:
    if candidate is not None:
        match = task.candidate_matches.get(candidate.id)
        metadata = match.metadata if match else None
        if isinstance(metadata, Mapping):
            title = metadata.get("title") or metadata.get("name") or metadata.get("original_title")
            if title:
                return str(title)
        return candidate.display_name
    return None

def fallback_search_year(task: OrganizeSession, candidate: MediaCandidate | None) -> int | None:
    if candidate is None:
        return None
    match = task.candidate_matches.get(candidate.id)
    metadata = match.metadata if match else None
    if not isinstance(metadata, Mapping):
        return None
    return optional_int(metadata.get("release_year") or metadata.get("year"))

def require_tmdb_media_type(task: OrganizeSession, tmdb_candidate) -> None:
    if tmdb_candidate.media_type != task.media_type:
        raise OrganizeSessionError(
            f"TMDB ID {tmdb_candidate.tmdb_id} is {tmdb_candidate.media_type.value}; expected {task.media_type.value}"
        )

def extensions_from_candidate(media_candidate: MediaCandidate) -> MediaExtensionPolicy:
    video = frozenset(file.extension.lower() for file in media_candidate.files if not file.is_sidecar)
    subtitle = frozenset(file.extension.lower() for file in media_candidate.files if file.is_sidecar)
    return MediaExtensionPolicy(video=video, subtitle=subtitle, sidecar=frozenset())
