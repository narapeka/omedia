from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.domain.activity import ActivityArea, ActivityEvent, ActivityStatus
from app.domain.depot import Depot, ResolveMode
from app.domain.organize import OrganizePlanItem
from app.domain.result import ResultStatus
from app.engines.activity.provenance import compact_context, replacement_provenance
from app.engines.plan.movie.evidence import (
    movie_plan_extension,
    movie_plan_from_evidence,
    movie_plan_ignored_duplicate_subtitles,
    movie_plan_media_kind,
    movie_plan_part_token,
    movie_plan_primary_source,
)
from app.engines.plan.tv.evidence import (
    tv_episode_plan_extension,
    tv_episode_plan_from_evidence,
    tv_episode_plan_ignored_duplicate_subtitles,
    tv_episode_plan_int,
    tv_episode_plan_media_kind,
    tv_episode_plan_resolution_status,
)
from app.engines.scan.media import is_path_size_eligible_non_subtitle
from app.infra.fs.move import move_with_replace
from app.infra.fs.result import StorageMoveStatus
from app.services.activity.recorder import ActivityRecorder
from app.services.identify.evidence import match_evidence_summary_payload


@dataclass(frozen=True)
class OrganizeCandidateResult:
    candidate_id: str
    status: ResultStatus
    source_path: Path
    destination_path: Path | None = None
    activity_event: ActivityEvent | None = None
    message: str | None = None


class OrganizeMove:
    def __init__(
        self,
        *,
        candidate: OrganizePlanItem,
        depot: Depot,
        activity: ActivityRecorder,
        sidecar_extensions=frozenset(),
        subtitle_extensions=frozenset(),
        extensions=None,
        min_non_subtitle_file_size_bytes: int | None = None,
        area: ActivityArea,
        context: dict[str, Any] | None,
        source_root: Path | None,
    ) -> None:
        self.candidate = candidate
        self.depot = depot
        self.activity = activity
        self.sidecar_extensions = frozenset(sidecar_extensions)
        self.subtitle_extensions = frozenset(subtitle_extensions)
        self.extensions = extensions
        self.min_non_subtitle_file_size_bytes = min_non_subtitle_file_size_bytes
        self.area = area
        self.context = context
        self.source_root = source_root

    def run(self, *, summary: str | None = None) -> OrganizeCandidateResult:
        if self.candidate.preview.proposed_relative_path is None:
            return self._failed(None, "Candidate has no renderable destination")
        destination_path = self.depot.path / self.candidate.preview.proposed_relative_path
        ineligible = self._ineligible(destination_path)
        if ineligible is not None:
            return ineligible
        overwritten = destination_path.exists()
        move_context = self._context(destination_path)
        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            move_result = move_with_replace(
                self.candidate.source_path,
                destination_path,
                cleanup_root=self.source_root,
                sidecar_extensions=self.sidecar_extensions,
                subtitle_extensions=self.subtitle_extensions,
                min_non_subtitle_file_size_bytes=self.min_non_subtitle_file_size_bytes,
            )
            move_context = {**move_context, **move_result.context()}
            if move_result.status == StorageMoveStatus.SUCCEEDED:
                return self._success(
                    destination_path,
                    context=move_context,
                    summary=summary or ("Moved to Depot with replacement" if overwritten else "Moved to Depot"),
                )
            return self._move_failure(destination_path, move_result, context=move_context)
        except Exception as exc:
            return self._exception(destination_path, exc, context=move_context)

    def _ineligible(self, destination_path: Path) -> OrganizeCandidateResult | None:
        if self._source_size_eligible():
            return None
        return self._skip(
            destination_path,
            "below_min_non_subtitle_file_size",
            "Source file is below the configured minimum non-subtitle size",
            context={
                **(self.context or {}),
                "min_non_subtitle_file_size_bytes": self.min_non_subtitle_file_size_bytes,
            },
        )

    def _context(self, destination_path: Path) -> dict[str, Any]:
        return replacement_provenance(
            source_path=self.candidate.source_path,
            destination_path=destination_path,
            rule_context=rule_context(self.candidate),
            metadata_context=metadata_context(self.candidate),
            context=candidate_context(self.candidate, self.depot, context=self.context, source_root=self.source_root),
        )

    def _success(
        self,
        destination_path: Path,
        *,
        context: dict[str, Any],
        summary: str,
    ) -> OrganizeCandidateResult:
        entry = self.activity.record_depot_item(
            area=self.area,
            status=ActivityStatus.SUCCEEDED,
            source_path=self.candidate.source_path,
            destination_path=destination_path,
            summary=summary,
            depot=self.depot,
            context=context,
        )
        return OrganizeCandidateResult(
            self.candidate.id,
            ResultStatus.SUCCEEDED,
            self.candidate.source_path,
            destination_path,
            entry,
        )

    def _move_failure(self, destination_path: Path, move_result, *, context: dict[str, Any]) -> OrganizeCandidateResult:
        status = ResultStatus.TIMEOUT if move_result.status == StorageMoveStatus.TIMEOUT else ResultStatus.FAILED
        entry = self.activity.record_depot_item(
            area=self.area,
            status=ActivityStatus.FAILED,
            reason="timed_out" if move_result.status == StorageMoveStatus.TIMEOUT else move_result.error_type,
            source_path=self.candidate.source_path,
            destination_path=destination_path,
            summary=move_result.message,
            depot=self.depot,
            context={**context, "error_type": move_result.error_type},
        )
        return OrganizeCandidateResult(
            self.candidate.id,
            status,
            self.candidate.source_path,
            destination_path,
            entry,
            move_result.message,
        )

    def _exception(self, destination_path: Path, exc: Exception, *, context: dict[str, Any]) -> OrganizeCandidateResult:
        entry = self.activity.record_depot_item(
            area=self.area,
            status=ActivityStatus.FAILED,
            reason=type(exc).__name__,
            source_path=self.candidate.source_path,
            destination_path=destination_path,
            summary=str(exc),
            depot=self.depot,
            context={**context, "error_type": type(exc).__name__},
        )
        return OrganizeCandidateResult(
            self.candidate.id,
            ResultStatus.FAILED,
            self.candidate.source_path,
            destination_path,
            entry,
            str(exc),
        )

    def _skip(
        self,
        destination_path: Path,
        reason: str,
        summary: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> OrganizeCandidateResult:
        entry = self.activity.record_depot_item(
            area=self.area,
            status=ActivityStatus.SKIPPED,
            reason=reason,
            source_path=self.candidate.source_path,
            destination_path=destination_path,
            summary=summary,
            depot=self.depot,
            context=compact_context(
                {
                    "skip_reason": reason,
                    **candidate_context(self.candidate, self.depot, context=context, source_root=self.source_root),
                }
            ),
        )
        return OrganizeCandidateResult(
            self.candidate.id,
            ResultStatus.SKIPPED,
            self.candidate.source_path,
            destination_path,
            entry,
            summary,
        )

    def _failed(self, destination_path: Path | None, message: str) -> OrganizeCandidateResult:
        entry = self.activity.record_depot_item(
            area=self.area,
            status=ActivityStatus.FAILED,
            reason="invalid_destination",
            source_path=self.candidate.source_path,
            destination_path=destination_path,
            summary=message,
            context=candidate_context(self.candidate, None, context=self.context, source_root=self.source_root),
        )
        return OrganizeCandidateResult(self.candidate.id, ResultStatus.FAILED, self.candidate.source_path, destination_path, entry, message)

    def _source_size_eligible(self) -> bool:
        if not self.min_non_subtitle_file_size_bytes:
            return True
        extensions = self.extensions
        if extensions is None:
            from app.domain.media import MediaExtensionPolicy

            extensions = MediaExtensionPolicy(
                video=frozenset(),
                subtitle=self.subtitle_extensions,
                sidecar=self.sidecar_extensions,
            )
        return is_path_size_eligible_non_subtitle(
            self.candidate.source_path,
            extensions=extensions,
            min_non_subtitle_file_size_bytes=self.min_non_subtitle_file_size_bytes,
        )


def candidate_context(
    candidate: OrganizePlanItem,
    depot: Depot | None,
    *,
    context: dict[str, Any] | None = None,
    source_root: Path | None = None,
) -> dict:
    merged = dict(context or {})
    merged.update(
        {
            "candidate_id": candidate.id,
            "plan_item_id": candidate.id,
            "source_candidate_id": candidate.source_candidate_id,
            "source_file_id": candidate.source_file_id,
            "confidence": candidate.confidence.value,
            "user_decision": candidate.user_decision.value if candidate.user_decision else None,
            "metadata_source": candidate.metadata_source,
            "manual_override_tmdb_id": candidate.manual_override_tmdb_id,
            "source_relative_path": relative_path_text(candidate.source_path, source_root),
            "depot_relative_path": path_text(candidate.preview.proposed_relative_path),
            "destination_relative_path": path_text(candidate.preview.proposed_relative_path),
            "render_warnings": list(candidate.preview.render_warnings),
        }
    )
    merged.update(planned_media_context(candidate))
    if depot is not None:
        merged["depot_id"] = depot.id
        merged["depot_path"] = str(depot.path)
        merged["target_library_path"] = str(depot.policy.target_library_path)
        merged["media_type"] = depot.media_type.value
    return compact_context(merged)


def full_package_context(identity, key: str) -> dict[str, object]:
    return {
        "resolve_mode": ResolveMode.FULL.value,
        "resolve_identity_kind": identity.kind,
        "resolve_identity_key": identity.key,
        "resolve_scope": "package",
        "package_root_relative_path": identity.root_relative_path.as_posix(),
        "conflict_group_key": key,
    }


def planned_media_context(candidate: OrganizePlanItem) -> dict:
    if tv_episode_plan_from_evidence(candidate.evidence) is not None:
        return {
            "media_kind": tv_episode_plan_media_kind(candidate.evidence),
            "tv_planned_season": tv_episode_plan_int(candidate.evidence, "season"),
            "tv_planned_episode": tv_episode_plan_int(candidate.evidence, "episode"),
            "tv_planned_end_episode": tv_episode_plan_int(candidate.evidence, "end_episode"),
            "tv_resolution_status": tv_episode_plan_resolution_status(candidate.evidence),
            "planned_extension": tv_episode_plan_extension(candidate.evidence),
            "ignored_duplicate_subtitles": tv_episode_plan_ignored_duplicate_subtitles(candidate.evidence),
        }
    if movie_plan_from_evidence(candidate.evidence) is not None:
        return {
            "media_kind": movie_plan_media_kind(candidate.evidence),
            "movie_primary_source": movie_plan_primary_source(candidate.evidence),
            "movie_part_token": movie_plan_part_token(candidate.evidence),
            "planned_extension": movie_plan_extension(candidate.evidence),
            "ignored_duplicate_subtitles": movie_plan_ignored_duplicate_subtitles(candidate.evidence),
        }
    return {}


def rule_context(candidate: OrganizePlanItem) -> dict:
    return {
        "matched_category": candidate.preview.matched_category,
        "bucket": candidate.preview.preview_bucket,
    }


def metadata_context(candidate: OrganizePlanItem) -> dict:
    metadata = candidate.metadata or {}
    return {
        "metadata_tmdb_id": metadata.get("tmdb_id"),
        "metadata_title": metadata.get("title") or metadata.get("name"),
        "metadata_year": metadata.get("release_year") or metadata.get("year"),
        "metadata_source": candidate.metadata_source,
        "manual_override_tmdb_id": candidate.manual_override_tmdb_id,
        "evidence_summary": match_evidence_summary_payload(candidate.evidence),
    }


def relative_path_text(path: Path, root: Path | None) -> str | None:
    if root is None:
        return None
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def path_text(path: Path | None) -> str | None:
    return path.as_posix() if path is not None else None
