from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.core.path import render_tag_suffix
from app.domain.media import MediaType
from app.domain.organize import CandidatePreview, OrganizePlanItem
from app.engines.name.depot import split_depot_relative_path
from app.engines.plan.movie.evidence import movie_plan_tag, set_movie_plan_tag
from app.engines.plan.tv.evidence import set_tv_episode_plan_tag, tv_episode_plan_int, tv_episode_plan_tag

ResolveIdentityKind = Literal["movie_package", "tv_season_package", "tv_episode", "tv_episode_range"]


@dataclass(frozen=True)
class ResolveIdentity:
    kind: ResolveIdentityKind
    key: str
    root_relative_path: Path
    season: int | None = None
    episode: int | None = None
    end_episode: int | None = None
    covered_episode_keys: tuple[str, ...] = ()


def package_identity(item: OrganizePlanItem, media_type: MediaType) -> ResolveIdentity | None:
    relative_path = item.preview.proposed_relative_path
    if relative_path is None:
        return None
    relative_path = Path(relative_path)
    if media_type == MediaType.MOVIE:
        split = split_depot_relative_path(relative_path)
        root = split.media_root_relative_path or relative_path.parent
        return ResolveIdentity(
            kind="movie_package",
            key=f"movie:{root.as_posix()}",
            root_relative_path=root,
        )
    if media_type == MediaType.TV:
        root = relative_path.parent
        return ResolveIdentity(
            kind="tv_season_package",
            key=f"tv-season:{root.as_posix()}",
            root_relative_path=root,
            season=_tv_plan_int(item, "season"),
        )
    return None


def episode_identity(item: OrganizePlanItem) -> ResolveIdentity | None:
    relative_path = item.preview.proposed_relative_path
    if relative_path is None:
        return None
    season = _tv_plan_int(item, "season")
    episode = _tv_plan_int(item, "episode")
    if season is None or episode is None:
        return None
    end_episode = _tv_plan_int(item, "end_episode")
    if end_episode is not None and end_episode < episode:
        end_episode = episode
    season_root = Path(relative_path).parent
    covered = episode_keys(season_root, season, episode, end_episode)
    if end_episode and end_episode > episode:
        code = f"S{season:02d}E{episode:02d}-E{end_episode:02d}"
        kind: ResolveIdentityKind = "tv_episode_range"
        key_prefix = "tv-episode-range"
    else:
        code = f"S{season:02d}E{episode:02d}"
        kind = "tv_episode"
        key_prefix = "tv-episode"
    return ResolveIdentity(
        kind=kind,
        key=f"{key_prefix}:{season_root.as_posix()}/{code}",
        root_relative_path=season_root,
        season=season,
        episode=episode,
        end_episode=end_episode,
        covered_episode_keys=covered,
    )


def episode_keys(season_root: Path, season: int, episode: int, end_episode: int | None = None) -> tuple[str, ...]:
    end = max(episode, end_episode or episode)
    return tuple(f"{season_root.as_posix()}/S{season:02d}E{number:02d}" for number in range(episode, end + 1))


def episode_ranges_overlap(left: Iterable[str], right: Iterable[str]) -> bool:
    return bool(set(left) & set(right))


def planned_tag(item: OrganizePlanItem) -> str | None:
    return movie_plan_tag(item.evidence) or tv_episode_plan_tag(item.evidence)


def apply_tag_override_to_plan_item(item: OrganizePlanItem, media_type: MediaType, raw_tag: str | None) -> bool:
    identity = package_identity(item, media_type)
    if identity is None or item.preview.proposed_relative_path is None:
        return False
    tag_text = (raw_tag or "").strip()
    suffix = render_tag_suffix(tag_text) if tag_text else None
    relative_path = Path(item.preview.proposed_relative_path)
    if identity.kind == "movie_package":
        new_root = _root_with_tag(identity.root_relative_path, suffix)
        try:
            tail = relative_path.relative_to(identity.root_relative_path)
        except ValueError:
            return False
        new_relative_path = new_root / tail
    elif identity.kind == "tv_season_package":
        season_root = identity.root_relative_path
        if len(season_root.parts) < 2:
            return False
        show_root = season_root.parent
        new_show_root = _root_with_tag(show_root, suffix)
        try:
            tail = relative_path.relative_to(show_root)
        except ValueError:
            return False
        new_relative_path = new_show_root / tail
    else:
        return False
    item.preview = CandidatePreview(
        preview_bucket=item.preview.preview_bucket,
        matched_category=item.preview.matched_category,
        proposed_relative_path=new_relative_path,
        render_warnings=list(item.preview.render_warnings),
    )
    _set_plan_tag(item, tag_text or None, suffix)
    return True


def _root_with_tag(root: Path, suffix: str | None) -> Path:
    base_name = _strip_rendered_tag_suffix(root.name)
    new_name = f"{base_name} {suffix}" if suffix else base_name
    return root.parent / new_name if root.parent.parts else Path(new_name)


def _strip_rendered_tag_suffix(value: str) -> str:
    return re.sub(r"\s+\[[^\]]+\]$", "", value).strip()


def _set_plan_tag(item: OrganizePlanItem, raw_tag: str | None, suffix: str | None) -> None:
    set_movie_plan_tag(item.evidence, raw_tag, suffix)
    set_tv_episode_plan_tag(item.evidence, raw_tag, suffix)


def _tv_plan_int(item: OrganizePlanItem, key: str) -> int | None:
    return tv_episode_plan_int(item.evidence, key)

