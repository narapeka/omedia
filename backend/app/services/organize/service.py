from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.error import ConfigurationError, OmediaError
from app.domain.activity import ActivityAction, ActivityArea, ActivityEntityType, ActivityStatus
from app.domain.depot import Depot
from app.domain.match import ConfidenceLevel
from app.domain.media import MediaType
from app.domain.organize import CandidateDecision, SourceActionOperation, SourceActionStatus
from app.domain.origin import OrganizePolicy
from app.domain.rule import OrganizeRule
from app.engines.scan.source import scan_source_root
from app.services.config.settings import SettingsFile
from app.services.identify.preview import Preview
from app.services.identify.search import ManualTMDBSearchService
from app.services.organize.execute import OrganizeExecutionResult
from app.services.organize.identify import (
    apply_source_candidate_tmdb_override as apply_identify_tmdb_override,
    run_identify_phase,
    scan_session as run_scan_session,
    search_tmdb_candidates,
)
from app.services.organize.review import apply_conflict_review_action as apply_review_action
from app.services.organize.review import (
    set_plan_item_decision as set_review_plan_item_decision,
    set_source_candidate_decision as set_review_source_candidate_decision,
)
from app.services.organize.review import validate_accepted_conflict_scope
from app.services.organize.move import OrganizeCandidateResult
from app.services.organize.session import BulkSessionCreateResult, BulkSessions, SessionReads
from app.services.organize.source import (
    SourceEdit,
    source_candidate_detail,
    source_file_detail,
    source_action_activity,
)


@dataclass(frozen=True)
class OrganizeExecution:
    session_id: str
    result: OrganizeExecutionResult
    source_candidate_by_plan: dict[str, str | None]


@dataclass(frozen=True)
class DirectOrganizeResult:
    source: str
    progress: list[dict[str, Any]]
    candidates: int
    matched: int
    unmatched: int
    moved: int
    skipped: int
    failed: int
    results: list[OrganizeCandidateResult]


class OrganizeService:
    def __init__(
        self,
        *,
        configuration,
        sessions,
        settings: SettingsFile,
        match,
        organizer,
        activity,
        store,
    ) -> None:
        self.configuration = configuration
        self.sessions = sessions
        self.settings = settings
        self.match = match
        self.organizer = organizer
        self.activity = activity
        self.store = store
        self.views = SessionReads(configuration=configuration, sessions=sessions, settings=settings)
        self.bulk = BulkSessions(configuration=configuration, sessions=sessions, scan_session=self.scan_session)

    def update_matcher(self, match) -> None:
        self.match = match

    def active_sessions(self):
        return self.sessions.active_sessions()

    def get(self, session_id: str):
        return self.sessions.get(session_id)

    def cancel(self, session_id: str):
        return self.sessions.cancel(session_id)

    def create_session(
        self,
        *,
        origin_id: str | None,
        source_path: Path | None,
        media_type: MediaType | str | None,
        target_depot_id: str | None,
        organize_rule_id: str | None,
    ):
        if origin_id:
            origin = self.configuration.get_origin(origin_id)
            session = self.sessions.create_for_origin(origin)
        else:
            if not source_path or not media_type or not target_depot_id:
                raise ValueError("Ad hoc OrganizeSession requires source_path, media_type, and policy")
            target_depot = self.depot_for_ref(target_depot_id)
            session = self.sessions.create_ad_hoc(
                source_path=source_path,
                media_type=MediaType(media_type),
                policy=OrganizePolicy(
                    target_depot_id=target_depot.id,
                    organize_rule_id=organize_rule_id,
                ),
                watch_settings=self.configuration.get_watch_settings(),
                origins=self.configuration.list_origins(),
                depots=self.configuration.list_depots(),
            )
        return self.scan_session(session.id)

    def create_sessions_bulk(self, origin_ids: list[str]) -> BulkSessionCreateResult:
        return self.bulk.create(origin_ids)

    def scan_session(self, session_id: str):
        return run_scan_session(
            self.sessions,
            session_id,
            extensions=self.settings.organize.extensions,
            min_non_subtitle_file_size_bytes=self.settings.organize.min_non_subtitle_file_size_bytes,
        )

    def restart_scan(self, session_id: str):
        self.sessions.restart_scan(session_id)
        return self.scan_session(session_id)

    def identify_session(self, session_id: str):
        session = self.sessions.get(session_id)
        return run_identify_phase(
            self.sessions,
            session_id,
            matcher=self.match,
            extensions=self.settings.organize.extensions,
            organize_rule=self.organize_rule_for_session(session_id),
            target_depot=self.target_depot_for_session(session.id),
        )

    def source_candidate_detail(self, session_id: str, candidate_id: str):
        return source_candidate_detail(self.sessions.get(session_id), candidate_id)

    def source_file_detail(self, session_id: str, candidate_id: str, file_id: str):
        return source_file_detail(
            self.sessions.get(session_id),
            candidate_id,
            file_id,
            extensions=self.settings.organize.extensions,
        )

    def delete_source_file(self, session_id: str, candidate_id: str, file_id: str):
        updated = SourceEdit(
            self.sessions.get(session_id),
            candidate_id,
            extensions=self.settings.organize.extensions,
            organize_rule=self.organize_rule_for_session(session_id),
            tv_episode_planner=getattr(self.match, "tv_episode_planner", None),
            target_depot=self.target_depot_for_session(session_id),
        ).delete_file(file_id)
        self.record_source_action(updated)
        return updated

    def rename_source_file(self, session_id: str, candidate_id: str, file_id: str, new_name: str):
        updated = SourceEdit(
            self.sessions.get(session_id),
            candidate_id,
            extensions=self.settings.organize.extensions,
            organize_rule=self.organize_rule_for_session(session_id),
            tv_episode_planner=getattr(self.match, "tv_episode_planner", None),
            target_depot=self.target_depot_for_session(session_id),
        ).rename_file(file_id, new_name)
        self.record_source_action(updated)
        return updated

    def delete_source_candidate(self, session_id: str, candidate_id: str):
        updated = SourceEdit(
            self.sessions.get(session_id),
            candidate_id,
            target_depot=self.target_depot_for_session(session_id),
        ).delete_candidate()
        self.record_source_action(updated)
        return updated

    def rename_source_candidate(self, session_id: str, candidate_id: str, new_name: str):
        updated = SourceEdit(
            self.sessions.get(session_id),
            candidate_id,
            extensions=self.settings.organize.extensions,
            organize_rule=self.organize_rule_for_session(session_id),
            tv_episode_planner=getattr(self.match, "tv_episode_planner", None),
            target_depot=self.target_depot_for_session(session_id),
        ).rename_candidate(new_name)
        self.record_source_action(updated)
        return updated

    def set_plan_item_decision(self, session_id: str, plan_item_id: str, decision):
        session = self.sessions.get(session_id)
        set_review_plan_item_decision(
            session,
            plan_item_id,
            decision,
            target_depot=self.target_depot_for_session(session_id),
        )
        return session

    def set_source_candidate_decision(self, session_id: str, candidate_id: str, decision):
        return set_review_source_candidate_decision(
            self.sessions.get(session_id),
            candidate_id,
            decision,
            target_depot=self.target_depot_for_session(session_id),
        )

    def apply_conflict_review_action(
        self,
        session_id: str,
        *,
        identity_key: str,
        source_candidate_id: str,
        action: str,
        tag_override: str | None,
    ):
        return apply_review_action(
            self.sessions.get(session_id),
            identity_key=identity_key,
            source_candidate_id=source_candidate_id,
            action=action,
            tag_override=tag_override,
            target_depot=self.target_depot_for_session(session_id),
        )

    def search_tmdb(self, session_id: str, *, source_candidate_id: str | None, query: str | None, year: int | None, language: str | None, page: int):
        return search_tmdb_candidates(
            self.sessions.get(session_id),
            search_service=ManualTMDBSearchService(self.match.tmdb),
            query=query,
            year=year,
            language=language or self.default_tmdb_language(),
            page=page,
            source_candidate_id=source_candidate_id,
        )

    def apply_source_candidate_tmdb_override(self, session_id: str, candidate_id: str, *, tmdb_id: int):
        return apply_identify_tmdb_override(
            self.sessions.get(session_id),
            candidate_id,
            tmdb_id=tmdb_id,
            tmdb_client=self.match.tmdb,
            organize_rule=self.organize_rule_for_session(session_id),
            target_depot=self.target_depot_for_session(session_id),
            tv_episode_planner=getattr(self.match, "tv_episode_planner", None),
        )

    def execute_session(self, session_id: str) -> OrganizeExecution:
        current_session = self.sessions.get(session_id)
        depot = self.depot_for_ref(current_session.policy.target_depot_id)
        validate_accepted_conflict_scope(current_session, target_depot=depot)
        session = self.sessions.start_organize(session_id)
        origin = None
        try:
            origin = self.record_execution_started(session, depot)
            result, source_candidate_by_plan = self.execute_accepted_moves(session, depot)
        except Exception:
            self.sessions.fail_organize(session_id)
            self.record_execution_failed(session, depot, origin)
            raise
        self.sessions.finish(session_id)
        self.record_execution_finished(session, depot, result)
        return OrganizeExecution(
            session_id=session_id,
            result=result,
            source_candidate_by_plan=source_candidate_by_plan,
        )

    def organize_source_direct(
        self,
        *,
        source_path: Path,
        media_type: MediaType,
        policy: OrganizePolicy,
        depot: Depot,
        rule: OrganizeRule | None,
        source_label: str,
        context: dict[str, Any] | None = None,
    ) -> DirectOrganizeResult:
        media_candidates = scan_source_root(
            source_path,
            media_type,
            extensions=self.settings.organize.extensions,
            min_non_subtitle_file_size_bytes=self.settings.organize.min_non_subtitle_file_size_bytes,
        )
        results = self.match.match_batch(media_candidates)
        candidates = []
        for media_candidate in media_candidates:
            match_result = results.get(media_candidate.id)
            if match_result is None:
                continue
            candidates.extend(
                Preview.for_candidate(
                    media_candidate=media_candidate,
                    source_root=source_path,
                    match_result=match_result,
                    policy=policy,
                    organize_rule=rule,
                    extensions=self.settings.organize.extensions,
                    tv_episode_planner=getattr(self.match, "tv_episode_planner", None),
                )
            )
        accepted = []
        for candidate in candidates:
            if candidate.confidence == ConfidenceLevel.HIGH:
                candidate.user_decision = CandidateDecision.ACCEPT
                accepted.append(candidate)
        result = self.organizer.organize_candidates(accepted, depot, context=context, source_root=source_path)
        return DirectOrganizeResult(
            source=source_label,
            progress=[
                {"step": "scan", "candidates": len(media_candidates)},
                {"step": "identify", "candidates": len(candidates), "matched": len(accepted)},
                {"step": "organize", "moved": result.moved, "skipped": result.skipped, "failed": result.failed},
            ],
            candidates=len(candidates),
            matched=len(accepted),
            unmatched=len(candidates) - len(accepted),
            moved=result.moved,
            skipped=result.skipped,
            failed=result.failed,
            results=result.results,
        )

    def record_execution_started(self, session, depot):
        origin = self.configuration.get_origin(session.origin_id) if session.origin_id else None
        self.activity.record_session_event(
            area=ActivityArea.MANUAL_ORGANIZE,
            entity_type=ActivityEntityType.ORGANIZE_SESSION,
            action=ActivityAction.MOVE_TO_DEPOT,
            status=ActivityStatus.STARTED,
            trace_id=session.id,
            origin=origin,
            depot=depot,
            context={
                "origin_id": session.origin_id,
                "origin_path": str(session.path) if session.origin_id else None,
                "organize_rule_id": session.policy.organize_rule_id,
                "media_type": session.media_type.value,
            },
        )
        return origin

    def execute_accepted_moves(self, session, depot):
        context = {
            "origin_id": session.origin_id,
            "origin_path": str(session.path) if session.origin_id else None,
            "organize_rule_id": session.policy.organize_rule_id,
            "trace_id": session.id,
        }
        plan_items = [item for item in session.plan_items if item.user_decision == CandidateDecision.ACCEPT]
        source_candidate_by_plan = {item.id: item.source_candidate_id for item in plan_items}
        result = self.organizer.organize_candidates(
            plan_items,
            depot,
            context=context,
            source_root=session.path,
            resolve_decisions={
                key: "replace"
                for key, state in session.conflict_review_states.items()
                if state.replace
            },
        )
        return result, source_candidate_by_plan

    def record_execution_failed(self, session, depot, origin) -> None:
        self.activity.record_session_event(
            area=ActivityArea.MANUAL_ORGANIZE,
            entity_type=ActivityEntityType.ORGANIZE_SESSION,
            action=ActivityAction.MOVE_TO_DEPOT,
            status=ActivityStatus.FAILED,
            trace_id=session.id,
            summary="Organize session failed",
            origin=origin,
            depot=depot,
            context={"origin_id": session.origin_id, "media_type": session.media_type.value},
        )

    def record_execution_finished(self, session, depot, result) -> None:
        self.activity.record_session_event(
            area=ActivityArea.MANUAL_ORGANIZE,
            entity_type=ActivityEntityType.ORGANIZE_SESSION,
            action=ActivityAction.MOVE_TO_DEPOT,
            status=ActivityStatus.FAILED if result.failed else ActivityStatus.SUCCEEDED if result.moved else ActivityStatus.SKIPPED,
            trace_id=session.id,
            summary=organize_summary(result.moved, result.skipped, result.failed),
            origin=self.configuration.get_origin(session.origin_id) if session.origin_id else None,
            depot=depot,
            context={
                "moved": result.moved,
                "skipped": result.skipped,
                "failed": result.failed,
                "origin_id": session.origin_id,
                "media_type": session.media_type.value,
            },
        )

    def target_depot_for_session(self, session_id: str):
        session = self.sessions.get(session_id)
        try:
            return self.depot_for_ref(session.policy.target_depot_id)
        except OmediaError:
            return None

    def record_source_action(self, session) -> None:
        outcome = session.last_source_action_outcome
        if not outcome:
            return
        action = source_action_activity(session, outcome)
        if action is None:
            return
        try:
            origin = self.configuration.get_origin(session.origin_id) if session.origin_id else None
        except OmediaError:
            origin = None
        status, reason = activity_status_reason(action.status, action.blocked_reason)
        if action.operation == SourceActionOperation.RENAME:
            self.activity.record_rename(
                source_path=action.source_path,
                destination_path=action.destination_path,
                status=status,
                reason=reason,
                summary=action.message or "Renamed source item",
                trace_id=session.id,
                origin=origin,
                context=action.context,
            )
        elif action.operation == SourceActionOperation.DELETE:
            self.activity.record_delete(
                source_path=action.source_path,
                status=status,
                reason=reason,
                summary=action.message or "Deleted source item",
                trace_id=session.id,
                origin=origin,
                context=action.context,
            )

    def organize_rule_for_session(self, session_id: str):
        session = self.sessions.get(session_id)
        return (
            self.store.get_organize_rule(session.policy.organize_rule_id)
            if session.policy.organize_rule_id
            else None
        )

    def default_tmdb_language(self) -> str:
        languages = getattr(self.match, "languages", ())
        return str(languages[0]) if languages else "zh-CN"

    def depot_for_ref(self, depot_ref: str):
        try:
            return self.configuration.get_depot(depot_ref)
        except ConfigurationError:
            for depot in self.configuration.list_depots():
                if depot.name.casefold() == depot_ref.strip().casefold():
                    return depot
            raise ConfigurationError(
                f"No Depot configured for target: {depot_ref}",
                code="depot.no_target",
                details={"target": depot_ref},
            )


def activity_status_reason(status: SourceActionStatus, blocked_reason: object) -> tuple[ActivityStatus, str | None]:
    if status == SourceActionStatus.SUCCEEDED:
        return ActivityStatus.SUCCEEDED, None
    if status == SourceActionStatus.MISSING:
        return ActivityStatus.SKIPPED, "source_missing"
    if status == SourceActionStatus.BLOCKED:
        return ActivityStatus.SKIPPED, "blocked"
    return ActivityStatus.FAILED, str(blocked_reason) if blocked_reason else None


def organize_summary(moved: int, skipped: int, failed: int) -> str:
    pieces = [
        count_label(moved, "file moved to Depot", "files moved to Depot"),
        count_label(skipped, "skipped", "skipped"),
        count_label(failed, "failed", "failed"),
    ]
    return ", ".join(piece for piece in pieces if piece) or "No files moved to Depot"


def count_label(count: int, singular: str, plural: str) -> str | None:
    if count <= 0:
        return None
    return f"{count} {singular if count == 1 else plural}"

