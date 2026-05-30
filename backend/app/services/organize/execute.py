from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.domain.activity import ActivityArea, ActivityStatus
from app.domain.depot import Depot, ResolveMode, effective_depot_resolve_mode
from app.domain.media import MediaType
from app.domain.organize import CandidateDecision, OrganizePlanItem
from app.domain.result import ResultStatus
from app.engines.activity.provenance import compact_context
from app.engines.plan.tv.parser import extract_episode_info
from app.engines.resolve.identity import episode_identity, package_identity
from app.infra.fs.delete import StorageDeleteStatus, delete_verified_tree
from app.services.activity.recorder import ActivityRecorder
from app.services.depot.lock import DepotLockRegistry
from app.services.organize.move import OrganizeCandidateResult, OrganizeMove, candidate_context, full_package_context


@dataclass(frozen=True)
class OrganizeExecutionResult:
    moved: int = 0
    skipped: int = 0
    failed: int = 0
    results: list[OrganizeCandidateResult] = field(default_factory=list)


class OrganizeExecutor:
    def __init__(
        self,
        *,
        locks: DepotLockRegistry,
        activity: ActivityRecorder,
        sidecar_extensions=frozenset(),
        subtitle_extensions=frozenset(),
        extensions=None,
        min_non_subtitle_file_size_bytes: int | None = None,
    ):
        self.locks = locks
        self.activity = activity
        self.sidecar_extensions = frozenset(sidecar_extensions)
        self.subtitle_extensions = frozenset(subtitle_extensions)
        self.extensions = extensions
        self.min_non_subtitle_file_size_bytes = min_non_subtitle_file_size_bytes

    def update_media_policy(
        self,
        *,
        extensions=None,
        sidecar_extensions=frozenset(),
        subtitle_extensions=frozenset(),
        min_non_subtitle_file_size_bytes: int | None = None,
    ) -> None:
        self.extensions = extensions
        self.sidecar_extensions = frozenset(sidecar_extensions)
        self.subtitle_extensions = frozenset(subtitle_extensions)
        self.min_non_subtitle_file_size_bytes = min_non_subtitle_file_size_bytes

    def organize_candidates(
        self,
        candidates: list[OrganizePlanItem],
        depot: Depot,
        *,
        area: ActivityArea = ActivityArea.MANUAL_ORGANIZE,
        context: dict[str, Any] | None = None,
        source_root: Path | None = None,
        resolve_decisions: Mapping[str, str] | None = None,
    ) -> OrganizeExecutionResult:
        mode = effective_depot_resolve_mode(depot)
        if depot.media_type == MediaType.TV and mode == ResolveMode.INCREMENTAL:
            results = self._organize_incremental_candidates(
                candidates,
                depot,
                area=area,
                context=context,
                source_root=source_root,
            )
        else:
            results = self._organize_full_candidates(
                candidates,
                depot,
                area=area,
                context=context,
                source_root=source_root,
                resolve_decisions=resolve_decisions or {},
            )
        return OrganizeExecutionResult(
            moved=sum(1 for result in results if result.status == ResultStatus.SUCCEEDED),
            skipped=sum(1 for result in results if result.status == ResultStatus.SKIPPED),
            failed=sum(1 for result in results if result.status in {ResultStatus.FAILED, ResultStatus.TIMEOUT}),
            results=results,
        )

    def _organize_full_candidates(
        self,
        candidates: list[OrganizePlanItem],
        depot: Depot,
        *,
        area: ActivityArea,
        context: dict[str, Any] | None,
        source_root: Path | None,
        resolve_decisions: Mapping[str, str],
    ) -> list[OrganizeCandidateResult]:
        passthrough, groups = self._group_full_package_candidates(candidates, depot)
        results: list[OrganizeCandidateResult] = []
        for candidate in passthrough:
            results.append(self.organize_candidate(candidate, depot, area=area, context=context, source_root=source_root))
        for key, items in groups.items():
            identity = package_identity(items[0], depot.media_type)
            if identity is None:
                continue
            source_ids = {item.source_candidate_id for item in items if item.source_candidate_id}
            destination_root = depot.path / identity.root_relative_path
            group_context = full_package_context(identity, key)
            if len(source_ids) > 1:
                results.extend(self._skip_duplicate_source_package(items, depot, destination_root, area=area, context={**(context or {}), **group_context}, source_root=source_root))
                continue
            replace_package = resolve_decisions.get(key) == "replace"
            if destination_root.exists() and not replace_package:
                results.extend(self._skip_existing_package(items, depot, destination_root, area=area, context={**(context or {}), **group_context}, source_root=source_root))
                continue
            if destination_root.exists() and replace_package:
                replace_context, failures = self._replace_existing_package(
                    items,
                    depot,
                    destination_root,
                    area=area,
                    context={**(context or {}), **group_context},
                    source_root=source_root,
                )
                if failures:
                    results.extend(failures)
                    continue
                group_context = {**group_context, **replace_context}
            for item in sorted(items, key=_organize_item_sort_key):
                results.append(
                    self._move(
                        item,
                        depot,
                        area=area,
                        context={**(context or {}), **group_context},
                        source_root=source_root,
                    )
                )
        return results

    def _group_full_package_candidates(
        self,
        candidates: list[OrganizePlanItem],
        depot: Depot,
    ) -> tuple[list[OrganizePlanItem], dict[str, list[OrganizePlanItem]]]:
        groups: dict[str, list[OrganizePlanItem]] = {}
        passthrough: list[OrganizePlanItem] = []
        for candidate in candidates:
            identity = package_identity(candidate, depot.media_type)
            if identity is None:
                passthrough.append(candidate)
                continue
            groups.setdefault(identity.key, []).append(candidate)
        return passthrough, groups

    def _skip_duplicate_source_package(
        self,
        items: list[OrganizePlanItem],
        depot: Depot,
        destination_root: Path,
        *,
        area: ActivityArea,
        context: dict[str, Any],
        source_root: Path | None,
    ) -> list[OrganizeCandidateResult]:
        return [
            self._skip_candidate(
                item,
                depot,
                destination_root / item.preview.proposed_relative_path.name if item.preview.proposed_relative_path else destination_root,
                "package_conflict",
                "Multiple accepted source packages target the same package",
                area=area,
                context={**context, "package_conflict_reason": "duplicate_source_package"},
                source_root=source_root,
            )
            for item in items
        ]

    def _skip_existing_package(
        self,
        items: list[OrganizePlanItem],
        depot: Depot,
        destination_root: Path,
        *,
        area: ActivityArea,
        context: dict[str, Any],
        source_root: Path | None,
    ) -> list[OrganizeCandidateResult]:
        skip_context = {**context, "package_conflict_reason": "package_exists"}
        if depot.media_type == MediaType.MOVIE:
            skip_context.update(
                {
                    "skip_reason": "movie_origin_depot_resolve_disabled",
                    "movie_origin_depot_resolve_disabled": True,
                }
            )
        return [
            self._skip_candidate(
                item,
                depot,
                depot.path / item.preview.proposed_relative_path if item.preview.proposed_relative_path else destination_root,
                "package_conflict",
                "Target package already exists",
                area=area,
                context=skip_context,
                source_root=source_root,
            )
            for item in items
        ]

    def _replace_existing_package(
        self,
        items: list[OrganizePlanItem],
        depot: Depot,
        destination_root: Path,
        *,
        area: ActivityArea,
        context: dict[str, Any],
        source_root: Path | None,
    ) -> tuple[dict[str, object], list[OrganizeCandidateResult]]:
        delete_result = delete_verified_tree(destination_root, protected_root=depot.path)
        if delete_result.status in {StorageDeleteStatus.SUCCEEDED, StorageDeleteStatus.MISSING}:
            return {**delete_result.context(), "package_replaced": True}, []
        failures = [
            self._failed(
                item,
                depot.path / item.preview.proposed_relative_path if item.preview.proposed_relative_path else destination_root,
                delete_result.message,
                area=area,
                context={**context, **delete_result.context()},
                source_root=source_root,
            )
            for item in items
        ]
        return {}, failures

    def _organize_incremental_candidates(
        self,
        candidates: list[OrganizePlanItem],
        depot: Depot,
        *,
        area: ActivityArea,
        context: dict[str, Any] | None,
        source_root: Path | None,
    ) -> list[OrganizeCandidateResult]:
        groups: list[tuple[tuple[float, str], tuple[str, ...], list[OrganizePlanItem]]] = []
        grouped: dict[tuple[str | None, tuple[str, ...]], list[OrganizePlanItem]] = {}
        for candidate in candidates:
            identity = episode_identity(candidate)
            if identity is None:
                grouped[(candidate.source_candidate_id, (candidate.id,))] = [candidate]
                continue
            grouped.setdefault((candidate.source_candidate_id, identity.covered_episode_keys), []).append(candidate)
        for (_source_candidate_id, covered_keys), items in grouped.items():
            sort_key = max((_organize_item_sort_key(item) for item in items), default=(0, ""))
            groups.append((sort_key, covered_keys, items))
        groups.sort(key=lambda item: item[0])

        results: list[OrganizeCandidateResult] = []
        with self.locks.acquire(depot):
            for _sort_key, covered_keys, items in groups:
                identity = episode_identity(items[0])
                if identity is None:
                    for item in sorted(items, key=_organize_item_sort_key):
                        results.append(self._move(item, depot, area=area, context=context, source_root=source_root))
                    continue
                destination_root = depot.path / identity.root_relative_path
                deleted = _delete_overlapping_episode_files(destination_root, covered_keys)
                group_context = {
                    **(context or {}),
                    "resolve_mode": ResolveMode.INCREMENTAL.value,
                    "resolve_identity_kind": identity.kind,
                    "resolve_identity_key": identity.key,
                    "resolve_scope": "episode",
                    "episode_key": ",".join(identity.covered_episode_keys),
                    "tv_planned_season": identity.season,
                    "tv_planned_episode": identity.episode,
                    "tv_planned_end_episode": identity.end_episode,
                    "incremental_deleted_existing": [path.as_posix() for path in deleted],
                }
                for item in sorted(items, key=_organize_item_sort_key):
                    results.append(
                        self._move(
                            item,
                            depot,
                            area=area,
                            context=group_context,
                            source_root=source_root,
                            summary="Moved to Depot updating episode",
                        )
                    )
        return results

    def organize_candidate(
        self,
        candidate: OrganizePlanItem,
        depot: Depot,
        *,
        area: ActivityArea = ActivityArea.MANUAL_ORGANIZE,
        context: dict[str, Any] | None = None,
        source_root: Path | None = None,
    ) -> OrganizeCandidateResult:
        if candidate.user_decision != CandidateDecision.ACCEPT:
            return OrganizeCandidateResult(
                candidate_id=candidate.id,
                status=ResultStatus.SKIPPED,
                source_path=candidate.source_path,
                message="Candidate is not accepted",
            )
        if candidate.preview.proposed_relative_path is None:
            return self._failed(
                candidate,
                None,
                "Candidate has no renderable destination",
                area=area,
                context=context,
                source_root=source_root,
            )
        destination_path = depot.path / candidate.preview.proposed_relative_path
        if not candidate.source_path.exists():
            entry = self.activity.record_depot_item(
                area=area,
                status=ActivityStatus.SKIPPED,
                reason="source_missing",
                source_path=candidate.source_path,
                destination_path=destination_path,
                summary="Source file no longer exists",
                depot=depot,
                context=candidate_context(candidate, depot, context=context, source_root=source_root),
            )
            return OrganizeCandidateResult(candidate.id, ResultStatus.SKIPPED, candidate.source_path, destination_path, entry)

        with self.locks.acquire(depot):
            movie_identity = package_identity(candidate, MediaType.MOVIE) if depot.media_type == MediaType.MOVIE else None
            movie_destination_exists = (depot.path / movie_identity.root_relative_path).exists() if movie_identity else destination_path.exists()
            if depot.media_type == MediaType.MOVIE and movie_destination_exists:
                entry = self.activity.record_depot_item(
                    area=area,
                    status=ActivityStatus.SKIPPED,
                    reason="resolve_disabled",
                    source_path=candidate.source_path,
                    destination_path=destination_path,
                    summary="Movie Origin to Depot resolve disabled",
                    depot=depot,
                    context=compact_context(
                        {
                            **candidate_context(candidate, depot, context=context, source_root=source_root),
                            "skip_reason": "movie_origin_depot_resolve_disabled",
                            "movie_origin_depot_resolve_disabled": True,
                        }
                    ),
                )
                return OrganizeCandidateResult(
                    candidate.id,
                    ResultStatus.SKIPPED,
                    candidate.source_path,
                    destination_path,
                    entry,
                    "Movie Origin to Depot resolve disabled",
                )
            return self._move(
                candidate,
                depot,
                area=area,
                context=context,
                source_root=source_root,
            )

    def _move(
        self,
        candidate: OrganizePlanItem,
        depot: Depot,
        *,
        area: ActivityArea,
        context: dict[str, Any] | None,
        source_root: Path | None,
        summary: str | None = None,
    ) -> OrganizeCandidateResult:
        return OrganizeMove(
            candidate=candidate,
            depot=depot,
            activity=self.activity,
            sidecar_extensions=self.sidecar_extensions,
            subtitle_extensions=self.subtitle_extensions,
            extensions=self.extensions,
            min_non_subtitle_file_size_bytes=self.min_non_subtitle_file_size_bytes,
            area=area,
            context=context,
            source_root=source_root,
        ).run(summary=summary)

    def _skip_candidate(
        self,
        candidate: OrganizePlanItem,
        depot: Depot,
        destination_path: Path,
        reason: str,
        summary: str,
        *,
        area: ActivityArea,
        context: dict[str, Any] | None,
        source_root: Path | None,
    ) -> OrganizeCandidateResult:
        entry = self.activity.record_depot_item(
            area=area,
            status=ActivityStatus.SKIPPED,
            reason=reason,
            source_path=candidate.source_path,
            destination_path=destination_path,
            summary=summary,
            depot=depot,
            context=compact_context(
                {
                    "skip_reason": reason,
                    **candidate_context(candidate, depot, context=context, source_root=source_root),
                }
            ),
        )
        return OrganizeCandidateResult(
            candidate.id,
            ResultStatus.SKIPPED,
            candidate.source_path,
            destination_path,
            entry,
            summary,
        )

    def _failed(
        self,
        candidate: OrganizePlanItem,
        destination_path: Path | None,
        message: str,
        *,
        area: ActivityArea = ActivityArea.MANUAL_ORGANIZE,
        context: dict[str, Any] | None = None,
        source_root: Path | None = None,
    ) -> OrganizeCandidateResult:
        entry = self.activity.record_depot_item(
            area=area,
            status=ActivityStatus.FAILED,
            reason="invalid_destination",
            source_path=candidate.source_path,
            destination_path=destination_path,
            summary=message,
            context=candidate_context(candidate, None, context=context, source_root=source_root),
        )
        return OrganizeCandidateResult(candidate.id, ResultStatus.FAILED, candidate.source_path, destination_path, entry, message)


def _organize_item_sort_key(item: OrganizePlanItem) -> tuple[float, str]:
    mtime = item.source_mtime
    if mtime is None:
        try:
            mtime = item.source_path.stat().st_mtime
        except OSError:
            mtime = 0
    return (float(mtime or 0), item.source_path.as_posix().casefold())


def _delete_overlapping_episode_files(season_root: Path, covered_keys: tuple[str, ...]) -> list[Path]:
    if not season_root.exists() or not season_root.is_dir():
        return []
    covered_episode_codes = _episode_code_set(covered_keys)
    deleted: list[Path] = []
    for child in sorted(season_root.iterdir(), key=lambda path: path.name.casefold()):
        if not child.is_file():
            continue
        child_keys = _episode_keys_from_filename(season_root, child.name)
        if not child_keys or not covered_episode_codes.intersection(_episode_code_set(child_keys)):
            continue
        child.unlink()
        deleted.append(child.relative_to(season_root.parent.parent if len(season_root.parts) >= 2 else season_root.parent))
    return deleted


def _episode_keys_from_filename(season_root: Path, filename: str) -> tuple[str, ...]:
    parsed = extract_episode_info(filename)
    if parsed.season is None or parsed.episode is None:
        return ()
    return tuple(
        f"{season_root.as_posix()}/S{parsed.season:02d}E{episode:02d}"
        for episode in range(parsed.episode, (parsed.end_episode or parsed.episode) + 1)
    )


def _episode_code_set(keys: tuple[str, ...]) -> set[str]:
    return {key.rsplit("/", 1)[-1] for key in keys if key}
