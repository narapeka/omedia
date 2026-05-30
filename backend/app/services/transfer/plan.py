from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.core.path import normalized_path_key
from app.domain.activity import ActivityStatus
from app.domain.depot import Depot, ResolveMode, effective_depot_resolve_mode
from app.domain.media import DiskFileEntry, MediaType
from app.domain.rule import TransferRule
from app.engines.activity.provenance import replacement_provenance
from app.engines.name.depot import (
    DepotRelativePathParts,
    group_for_organize_prefix,
    join_relative_fragments,
    parse_system_media_root_name,
    split_depot_relative_path,
)
from app.engines.plan.tv.parser import extract_episode_info
from app.engines.resolve.identity import episode_ranges_overlap
from app.engines.rule.transfer import TransferRuleContext, TransferRuleEngine
from app.infra.fs.delete import StorageDeleteStatus, delete_verified_tree

@dataclass(frozen=True)
class TransferPlan:
    file: DiskFileEntry
    split: DepotRelativePathParts
    rule_result: object
    destination_relative_path: Path
    destination: Path
    cleanup_stop_root: Path
    package_root: Path | None = None
    package_kind: str | None = None
    episode_keys: tuple[str, ...] = ()
    destination_preexisting: bool = False
    destination_preexisting_size: int | None = None
    blocked_reason: str | None = None
    blocked_message: str | None = None

@dataclass(frozen=True)
class TransferPlanBlock:
    status: ActivityStatus
    reason: str
    summary: str
    context: dict = field(default_factory=dict)

def build_plan(
    file: DiskFileEntry,
    depot: Depot,
    *,
    transfer_rule: TransferRule | None,
    engine: TransferRuleEngine,
) -> TransferPlan:
    split = split_depot_relative_path(file.relative_path)
    rule_result = engine.match(
        transfer_rule,
        TransferRuleContext(
            relative_path=file.relative_path,
            media_relative_path=split.media_relative_path,
            organize_prefix=split.organize_prefix,
        ),
    )
    destination_relative_path_value = destination_relative_path(
        organize_prefix=split.organize_prefix,
        transfer_bucket=rule_result.bucket,
        media_relative_path=split.media_relative_path,
    )
    destination = depot.policy.target_library_path / destination_relative_path_value
    cleanup_stop_root = depot.path / split.organize_prefix if split.organize_prefix.parts else depot.path
    package_root, package_kind, blocked_reason = _transfer_package_root(depot, destination, split)
    episode_keys_value = _transfer_episode_keys(destination.parent, file.relative_path.name) if depot.media_type == MediaType.TV else ()
    preexisting_size = _file_size(destination) if destination.exists() and destination.is_file() else None
    return TransferPlan(
        file=file,
        split=split,
        rule_result=rule_result,
        destination_relative_path=destination_relative_path_value,
        destination=destination,
        cleanup_stop_root=cleanup_stop_root,
        package_root=package_root,
        package_kind=package_kind,
        episode_keys=episode_keys_value,
        destination_preexisting=destination.exists(),
        destination_preexisting_size=preexisting_size,
        blocked_reason=blocked_reason,
        blocked_message="Movie Transfer requires a package folder" if blocked_reason else None,
    )

def plan_context(
    job: TransferJob,
    depot: Depot,
    plan: TransferPlan,
    transfer_rule: TransferRule | None,
) -> dict:
    split = plan.split
    rule_result = plan.rule_result
    group = group_for_organize_prefix(depot.id, split.organize_prefix)
    return replacement_provenance(
        source_path=plan.file.path,
        destination_path=plan.destination,
        rule_context={
            "transfer_rule_id": transfer_rule.id if transfer_rule else depot.policy.transfer_rule_id,
            "matched_category": rule_result.matched_category,
            "transfer_bucket": rule_result.bucket,
            "variables": rule_result.variables,
        },
        metadata_context={
            **_metadata_from_depot_relative_path(split),
            "media_type": depot.media_type.value,
        },
        context={
            "depot_id": depot.id,
            "depot_name": depot.name,
            "depot_path": str(depot.path),
            "target_library_path": str(depot.policy.target_library_path),
            "depot_relative_path": plan.file.relative_path.as_posix(),
            "organize_prefix": split.organize_prefix.as_posix() if split.organize_prefix.parts else "",
            "candidate_group_key": group.key if group else None,
            "media_relative_path": split.media_relative_path.as_posix(),
            "path_split_confidence": split.confidence,
            "destination_relative_path": plan.destination_relative_path.as_posix(),
            "resolve_mode": effective_depot_resolve_mode(depot).value,
            "resolve_identity_kind": plan.package_kind,
            "package_root_relative_path": _relative_path_text(plan.package_root, depot.policy.target_library_path) if plan.package_root else None,
            "episode_key": ",".join(plan.episode_keys) if plan.episode_keys else None,
            "trace_id": job.id,
        },
    )

def prepare_replace_roots(depot: Depot, plans: list[TransferPlan]) -> dict[str, TransferPlanBlock]:
    blocks: dict[str, TransferPlanBlock] = {}
    for plan in plans:
        if plan.blocked_reason:
            blocks[plan_key(plan)] = TransferPlanBlock(
                status=ActivityStatus.SKIPPED,
                reason=plan.blocked_reason,
                summary=plan.blocked_message or "Transfer plan is blocked",
            )
    mode = effective_depot_resolve_mode(depot)
    if mode == ResolveMode.INCREMENTAL and depot.media_type == MediaType.TV:
        prepare_incremental_upserts([plan for plan in plans if plan_key(plan) not in blocks])
        return blocks
    plans_by_root: dict[str, list[TransferPlan]] = {}
    for plan in plans:
        if plan_key(plan) in blocks or plan.package_root is None:
            continue
        key = normalized_path_key(plan.package_root)
        plans_by_root.setdefault(key, []).append(plan)
    for root_plans in plans_by_root.values():
        package_root = root_plans[0].package_root
        if package_root is not None and package_root.exists():
            delete_result = delete_verified_tree(package_root, protected_root=depot.policy.target_library_path)
            if delete_result.status not in {StorageDeleteStatus.SUCCEEDED, StorageDeleteStatus.MISSING}:
                reason = delete_result.blocked_reason or delete_result.error_type or "package_delete_failed"
                for blocked_plan in root_plans:
                    blocks[plan_key(blocked_plan)] = TransferPlanBlock(
                        status=ActivityStatus.FAILED,
                        reason=reason,
                        summary=delete_result.message,
                        context=delete_result.context(),
                    )
    return blocks

def prepare_incremental_upserts(plans: list[TransferPlan]) -> None:
    ordered = sorted(plans, key=lambda plan: (float(plan.file.modified_time or 0), plan.file.path.as_posix().casefold()))
    for plan in ordered:
        if not plan.episode_keys:
            continue
        for existing in _overlapping_episode_files(plan.destination.parent, plan.episode_keys):
            existing.unlink()

def _transfer_package_root(depot: Depot, destination: Path, split: DepotRelativePathParts) -> tuple[Path | None, str | None, str | None]:
    if depot.media_type == MediaType.MOVIE:
        if len(split.media_relative_path.parts) < 2:
            return None, None, "movie_transfer_requires_package_folder"
        return destination.parent, "movie_package", None
    if depot.media_type == MediaType.TV and len(split.media_relative_path.parts) >= 3:
        return destination.parent, "tv_season_package", None
    return None, None, None

def _transfer_episode_keys(season_root: Path, filename: str) -> tuple[str, ...]:
    parsed = extract_episode_info(filename)
    if parsed.season is None or parsed.episode is None:
        return ()
    end = parsed.end_episode or parsed.episode
    return tuple(f"{season_root.as_posix()}/S{parsed.season:02d}E{episode:02d}" for episode in range(parsed.episode, end + 1))

def _overlapping_episode_files(season_root: Path, episode_keys_value: tuple[str, ...]) -> list[Path]:
    if not season_root.exists() or not season_root.is_dir():
        return []
    matches: list[Path] = []
    for child in sorted(season_root.iterdir(), key=lambda path: path.name.casefold()):
        if not child.is_file():
            continue
        child_keys = _transfer_episode_keys(season_root, child.name)
        if child_keys and episode_ranges_overlap(episode_keys_value, child_keys):
            matches.append(child)
    return matches

def _file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None

def plan_key(plan: TransferPlan) -> str:
    return normalized_path_key(plan.file.path)

def destination_relative_path(
    *,
    organize_prefix: Path | str,
    transfer_bucket: Path | str,
    media_relative_path: Path | str,
) -> Path:
    return join_relative_fragments(organize_prefix, transfer_bucket, media_relative_path)

def _metadata_from_depot_relative_path(relative_path: Path | DepotRelativePathParts) -> dict:
    split = relative_path if isinstance(relative_path, DepotRelativePathParts) else split_depot_relative_path(relative_path)
    media_root_name = split.media_root_name
    if media_root_name:
        metadata = parse_system_media_root_name(str(media_root_name))
        if metadata:
            return metadata
    for part in split.media_relative_path.parts:
        metadata = parse_system_media_root_name(part)
        if metadata:
            return metadata
    return {}

def _relative_path_text(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name
