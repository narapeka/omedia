from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from app.domain.depot import Depot
from app.domain.match import ConfidenceLevel, MatchResult
from app.domain.media import MediaCandidate, MediaExtensionPolicy, MediaType
from app.domain.organize import OrganizePlanItem, OrganizeSessionState
from app.domain.rule import OrganizeRule
from app.engines.scan.source import scan_source_root
from app.services.identify.candidate import CandidateMatch, candidate_match_from_result, metadata_from_tmdb_candidate
from app.services.identify.preview import Preview
from app.services.organize.session import SessionBook
from app.services.organize.plan import (
    active_media_candidate,
    apply_match_to_item,
    extensions_from_candidate,
    fallback_search_title,
    fallback_search_year,
    items_for_candidate,
    rebuild_source_candidate,
    require_tmdb_media_type,
)
from app.services.organize.candidate import (
    find_media_candidate,
    require_active_candidate,
    selected_source_candidate_ids as selected_candidates,
)
from app.services.organize.review import sort_plan_items
from app.services.organize.review import (
    apply_conflict_review_defaults,
    apply_existing_tag_overrides,
)
from app.services.organize.session import OrganizeSession, OrganizeSessionError, require_state

def scan_session(
    sessions: SessionBook,
    session_id: str,
    *,
    extensions: MediaExtensionPolicy,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> OrganizeSession:
    session = sessions.get(session_id)
    try:
        media_candidates = scan_source_root(
            session.path,
            session.media_type,
            extensions=extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )
    except Exception:
        sessions.cancel(session.id)
        raise
    return sessions.mark_scanned(session.id, media_candidates)

def run_identify_phase(
    sessions: SessionBook,
    session_id: str,
    *,
    matcher,
    extensions: MediaExtensionPolicy,
    organize_rule: OrganizeRule | None = None,
    target_depot: Depot | None = None,
) -> OrganizeSession:
    session = sessions.start_identify(session_id)
    try:
        selected_source_candidate_ids = selected_candidates(session)
        media_candidates = [
            active_media_candidate(session, candidate, extensions)
            for candidate in session.media_candidates
            if candidate.id in selected_source_candidate_ids
        ]
        media_candidates = [candidate for candidate in media_candidates if candidate is not None]
        match_results = matcher.match_batch(media_candidates)
        candidate_matches: dict[str, CandidateMatch] = {}
        plan_items: list[OrganizePlanItem] = []
        plan_items_by_candidate: dict[str, list[OrganizePlanItem]] = {}
        tv_episode_planner = getattr(matcher, "tv_episode_planner", None)

        matched_candidates: list[tuple[MediaCandidate, MatchResult]] = []
        for media_candidate in media_candidates:
            match_result = match_results.get(media_candidate.id)
            if match_result is None:
                continue
            match = candidate_match_from_result(media_candidate.id, match_result)
            candidate_matches[media_candidate.id] = match
            matched_candidates.append((media_candidate, match_result))

        workers = _identify_worker_count(len(matched_candidates))
        if workers <= 1:
            for media_candidate, match_result in matched_candidates:
                plan_items_by_candidate[media_candidate.id] = Preview.for_candidate(
                    media_candidate=media_candidate,
                    source_root=session.path,
                    match_result=match_result,
                    policy=session.policy,
                    organize_rule=organize_rule,
                    extensions=extensions,
                    tv_episode_planner=tv_episode_planner,
                )
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        Preview.for_candidate,
                        media_candidate=media_candidate,
                        source_root=session.path,
                        match_result=match_result,
                        policy=session.policy,
                        organize_rule=organize_rule,
                        extensions=extensions,
                        tv_episode_planner=tv_episode_planner,
                    ): media_candidate.id
                    for media_candidate, match_result in matched_candidates
                }
                for future in as_completed(futures):
                    plan_items_by_candidate[futures[future]] = future.result()

        for media_candidate, match_result in matched_candidates:
            plan_items.extend(plan_items_by_candidate.get(media_candidate.id, []))
        return sessions.mark_identified(
            session.id,
            candidate_matches=candidate_matches,
            plan_items=plan_items,
            selected_source_candidate_ids=selected_source_candidate_ids,
            target_depot=target_depot,
        )
    except Exception:
        sessions.fail_identify(session.id)
        raise


def search_tmdb_candidates(
    task: OrganizeSession,
    *,
    search_service,
    query: str | None = None,
    year: int | None = None,
    language: str = "zh-CN",
    page: int = 1,
    source_candidate_id: str | None = None,
):
    require_state(task, {OrganizeSessionState.SCANNED, OrganizeSessionState.IDENTIFIED})
    context_candidate = find_media_candidate(task, source_candidate_id) if source_candidate_id else None
    fallback_title = fallback_search_title(task, context_candidate)
    fallback_year = fallback_search_year(task, context_candidate)
    return search_service.search(
        media_type=task.media_type,
        query=query,
        year=year,
        language=language,
        page=page,
        fallback_title=fallback_title,
        fallback_year=fallback_year,
    )


def apply_source_candidate_tmdb_override(
    task: OrganizeSession,
    source_candidate_id: str,
    *,
    tmdb_id: int,
    tmdb_client,
    organize_rule: OrganizeRule | None = None,
    target_depot: Depot | None = None,
    tv_episode_planner=None,
) -> OrganizeSession:
    require_state(task, {OrganizeSessionState.IDENTIFIED})
    media_candidate = require_active_candidate(task, source_candidate_id)
    tmdb_candidate = tmdb_client.get_by_id(task.media_type, tmdb_id)
    if tmdb_candidate is None:
        raise OrganizeSessionError(f"TMDB ID not found: {tmdb_id}")
    require_tmdb_media_type(task, tmdb_candidate)
    match = CandidateMatch(
        source_candidate_id=source_candidate_id,
        confidence=ConfidenceLevel.HIGH,
        metadata=metadata_from_tmdb_candidate(tmdb_candidate),
        metadata_source="manual_override",
        manual_override_tmdb_id=str(tmdb_candidate.tmdb_id),
        evidence={"manual_override": {"tmdb_id": tmdb_candidate.tmdb_id}},
    )
    task.candidate_matches[source_candidate_id] = match
    if task.media_type == MediaType.TV and tv_episode_planner is not None:
        rebuild_source_candidate(
            task,
            source_candidate_id,
            extensions=extensions_from_candidate(media_candidate),
            organize_rule=organize_rule,
            tv_episode_planner=tv_episode_planner,
            target_depot=target_depot,
        )
        return task
    affected = [item for item in task.plan_items if item.source_candidate_id == source_candidate_id]
    if affected:
        for item in affected:
            apply_match_to_item(task, item, match, organize_rule=organize_rule)
    else:
        task.plan_items.extend(
            items_for_candidate(
                task,
                media_candidate,
                match,
                extensions=extensions_from_candidate(media_candidate),
                organize_rule=organize_rule,
                tv_episode_planner=None,
            )
        )
        task.plan_items = sort_plan_items(task.plan_items)
    apply_existing_tag_overrides(task, source_candidate_id=source_candidate_id)
    apply_conflict_review_defaults(task, target_depot=target_depot)
    return task


def _identify_worker_count(candidate_count: int) -> int:
    if candidate_count <= 1:
        return 1
    return min(8, candidate_count)
