from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.activity import ActivityArea
from app.domain.organize import CandidateDecision
from app.domain.result import ResultStatus
from app.domain.origin import Origin
from app.domain.media import MediaExtensionPolicy
from app.core.path import normalized_path_key
from app.engines.scan.source import scan_origin_candidate
from app.engines.scan.watch import scan_watch_source_packages
from app.services.activity.recorder import ActivityRecorder
from app.services.identify.preview import Preview
from app.services.organize.execute import OrganizeExecutor
from app.services.organize.move import OrganizeCandidateResult
from app.services.watch.buffer import WATCH_DISPATCH_SOURCE_MANUAL_POLL, WatchDispatch
from app.services.watch.returns import WatchReturn, watch_context


@dataclass(frozen=True)
class WatchRunResult:
    matched: int = 0
    unmatched: int = 0
    skipped: int = 0
    failed: int = 0
    organize_results: list[OrganizeCandidateResult] = field(default_factory=list)


class WatchOrganizeRun:
    def __init__(
        self,
        *,
        matcher,
        organizer: OrganizeExecutor,
        activity: ActivityRecorder,
        extensions: MediaExtensionPolicy,
        min_non_subtitle_file_size_bytes: int | None = None,
        depot_resolver,
        organize_rule_resolver=None,
    ):
        self.matcher = matcher
        self.organizer = organizer
        self.activity = activity
        self.extensions = extensions
        self.min_non_subtitle_file_size_bytes = min_non_subtitle_file_size_bytes
        self.depot_resolver = depot_resolver
        self.organize_rule_resolver = organize_rule_resolver or (lambda rule_id: None)

    def process_dispatches(self, dispatches: list[WatchDispatch]) -> WatchRunResult:
        deduped: dict[tuple[str, str], WatchDispatch] = {}
        for dispatch in dispatches:
            deduped[(dispatch.origin.id, normalized_path_key(dispatch.candidate_path))] = dispatch
        results = [self.process_candidate_dispatch(dispatch) for dispatch in deduped.values()]
        return WatchRunResult(
            matched=sum(result.matched for result in results),
            unmatched=sum(result.unmatched for result in results),
            skipped=sum(result.skipped for result in results),
            failed=sum(result.failed for result in results),
            organize_results=[item for result in results for item in result.organize_results],
        )

    def process_origin(self, origin: Origin) -> WatchRunResult:
        dispatches = [
            WatchDispatch(
                origin=origin,
                event_path=package.path,
                candidate_path=package.path,
                source=WATCH_DISPATCH_SOURCE_MANUAL_POLL,
                event_type="added",
                event_paths=(package.path,),
                rejected_reason=package.rejected_reason,
            )
            for package in scan_watch_source_packages(
                origin,
                self.extensions,
                min_non_subtitle_file_size_bytes=self.min_non_subtitle_file_size_bytes,
            )
        ]
        return self.process_dispatches(dispatches)

    def process_candidate_dispatch(self, dispatch: WatchDispatch) -> WatchRunResult:
        if dispatch.rejected_reason:
            outcome = WatchReturn(
                activity=self.activity,
                extensions=self.extensions,
                origin=dispatch.origin,
                source_path=dispatch.candidate_path,
                dispatch=dispatch,
                reason=dispatch.rejected_reason,
            ).move()
            if outcome == ResultStatus.SUCCEEDED:
                return WatchRunResult(unmatched=1)
            if outcome == ResultStatus.SKIPPED:
                return WatchRunResult(skipped=1)
            return WatchRunResult(failed=1)
        media_candidate = scan_origin_candidate(
            dispatch.origin,
            dispatch.candidate_path,
            self.extensions,
            min_non_subtitle_file_size_bytes=self.min_non_subtitle_file_size_bytes,
        )
        if media_candidate is None:
            return WatchRunResult()
        return self.process_candidate(dispatch.origin, media_candidate, dispatch)

    def process_candidate(
        self,
        origin: Origin,
        media_candidate,
        dispatch: WatchDispatch | None = None,
    ) -> WatchRunResult:
        matched = 0
        unmatched = 0
        skipped = 0
        failed = 0
        organize_results = []
        depot = self.depot_resolver(origin.policy.target_depot_id)
        organize_rule = self.organize_rule_resolver(origin.policy.organize_rule_id) if origin.policy.organize_rule_id else None
        match_result = self.matcher.match(media_candidate)
        if match_result.is_high_confidence:
            organize_candidates = Preview.for_candidate(
                media_candidate=media_candidate,
                source_root=origin.path,
                match_result=match_result,
                policy=origin.policy,
                organize_rule=organize_rule,
                extensions=self.extensions,
                tv_episode_planner=getattr(self.matcher, "tv_episode_planner", None),
            )
            for organize_candidate in organize_candidates:
                organize_candidate.user_decision = CandidateDecision.ACCEPT
            execution_result = self.organizer.organize_candidates(
                organize_candidates,
                depot,
                area=ActivityArea.WATCH_ORGANIZE,
                context={
                    **watch_context(origin, media_candidate.candidate_path, None, dispatch=dispatch),
                    "organize_rule_id": origin.policy.organize_rule_id,
                },
                source_root=origin.path,
            )
            organize_results.extend(execution_result.results)
            matched += execution_result.moved
            skipped += execution_result.skipped
            failed += execution_result.failed
            return WatchRunResult(matched, unmatched, skipped, failed, organize_results)

        outcome = WatchReturn(
            activity=self.activity,
            extensions=self.extensions,
            origin=origin,
            source_path=media_candidate.candidate_path,
            dispatch=dispatch,
        ).move()
        if outcome == ResultStatus.SUCCEEDED:
            unmatched += 1
        elif outcome == ResultStatus.SKIPPED:
            skipped += 1
        else:
            failed += 1
        return WatchRunResult(matched, unmatched, skipped, failed, organize_results)
