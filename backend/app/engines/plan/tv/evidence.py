from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from app.domain.organize import OrganizePlanItem
from app.domain.tv import TVEpisodeFile, episode_number_value

TV_EPISODE_PLAN_EVIDENCE_KEY = "tv_episode_plan"


def tv_episode_plan_evidence(episode: TVEpisodeFile) -> dict:
    return {
        "media_kind": episode.media_kind,
        "season": episode.season_number,
        "episode": episode.episode_number,
        "end_episode": episode.end_episode_number,
        "extension": episode.extension or episode.source_path.suffix,
        "is_sidecar": episode.is_sidecar,
        "confident": episode.confident,
        "episode_title": episode.title,
        "episode_title_source": episode.title_source or "none",
        "resolution": {
            "status": episode.resolution_status,
            "key": episode.resolution_key,
            "parser": episode.parser_result,
            "llm": episode.llm_result,
            "warning": episode.resolution_warning,
            "requested_keys": list(episode.resolution_requested_keys),
            "applied_keys": list(episode.resolution_applied_keys),
            "junk_keys": list(episode.resolution_junk_keys),
        },
        "inherited_from": episode.inherited_from,
        "ignored_duplicate_subtitles": list(episode.ignored_duplicate_subtitles),
    }


def tv_episode_plan_from_evidence(evidence: Mapping[str, Any]) -> Mapping[str, Any] | None:
    plan = evidence.get(TV_EPISODE_PLAN_EVIDENCE_KEY)
    return plan if isinstance(plan, Mapping) else None


def tv_episode_plan_media_kind(evidence: Mapping[str, Any]) -> str | None:
    return _optional_str(_tv_episode_plan_value(evidence, "media_kind"))


def tv_episode_plan_int(evidence: Mapping[str, Any], key: str) -> int | None:
    return episode_number_value(_tv_episode_plan_value(evidence, key))


def tv_episode_plan_resolution_status(evidence: Mapping[str, Any]) -> str | None:
    plan = tv_episode_plan_from_evidence(evidence)
    if plan is None:
        return None
    resolution = plan.get("resolution")
    if not isinstance(resolution, Mapping):
        return None
    return _optional_str(resolution.get("status"))


def tv_episode_plan_extension(evidence: Mapping[str, Any]) -> str | None:
    return _optional_str(_tv_episode_plan_value(evidence, "extension"))


def tv_episode_plan_tag(evidence: Mapping[str, Any]) -> str | None:
    return _optional_str(_tv_episode_plan_value(evidence, "tag"))


def tv_episode_plan_tag_suffix(evidence: Mapping[str, Any]) -> str | None:
    return _optional_str(_tv_episode_plan_value(evidence, "tag_suffix"))


def tv_episode_plan_ignored_duplicate_subtitles(evidence: Mapping[str, Any]) -> list[str]:
    return _string_list(_tv_episode_plan_value(evidence, "ignored_duplicate_subtitles"))


def set_tv_episode_plan_tag(evidence: MutableMapping[str, Any], raw_tag: str | None, suffix: str | None) -> bool:
    plan = _mutable_tv_episode_plan(evidence)
    if plan is None:
        return False
    if raw_tag:
        plan["tag"] = raw_tag
        plan["tag_suffix"] = suffix
    else:
        plan.pop("tag", None)
        plan.pop("tag_suffix", None)
    return True


def set_tv_episode_title_evidence(evidence: MutableMapping[str, Any], title: str | None, source: str) -> bool:
    plan = _mutable_tv_episode_plan(evidence)
    if plan is None:
        return False
    plan["episode_title"] = title
    plan["episode_title_source"] = source
    return True


def tv_episode_from_candidate(candidate: OrganizePlanItem) -> TVEpisodeFile | None:
    plan = tv_episode_plan_from_evidence(candidate.evidence)
    if plan is None:
        return None
    season = episode_number_value(plan.get("season"))
    episode = episode_number_value(plan.get("episode"))
    if season is None or episode is None:
        return None
    extension = plan.get("extension")
    media_kind = str(plan.get("media_kind") or ("subtitle" if plan.get("is_sidecar") else "video"))
    ignored_duplicate_subtitles = plan.get("ignored_duplicate_subtitles")
    resolution = plan.get("resolution")
    resolution = resolution if isinstance(resolution, Mapping) else {}
    return TVEpisodeFile(
        source_path=candidate.source_path,
        season_number=season,
        episode_number=episode,
        end_episode_number=episode_number_value(plan.get("end_episode")),
        extension=str(extension) if extension else candidate.source_path.suffix,
        title=str(plan.get("episode_title")) if plan.get("episode_title") else None,
        title_source=str(plan.get("episode_title_source")) if plan.get("episode_title_source") else None,
        is_sidecar=bool(plan.get("is_sidecar")),
        media_kind=media_kind,
        confident=bool(plan.get("confident")),
        ignored_duplicate_subtitles=[
            str(item)
            for item in ignored_duplicate_subtitles
            if item is not None
        ]
        if isinstance(ignored_duplicate_subtitles, list)
        else [],
        resolution_status=str(resolution.get("status") or "not_needed"),
        resolution_key=str(resolution.get("key")) if resolution.get("key") else None,
        parser_result=dict(resolution.get("parser")) if isinstance(resolution.get("parser"), Mapping) else None,
        llm_result=dict(resolution.get("llm")) if isinstance(resolution.get("llm"), Mapping) else None,
        resolution_warning=str(resolution.get("warning")) if resolution.get("warning") else None,
        resolution_requested_keys=_string_list(resolution.get("requested_keys")),
        resolution_applied_keys=_string_list(resolution.get("applied_keys")),
        resolution_junk_keys=_string_list(resolution.get("junk_keys")),
        inherited_from=str(plan.get("inherited_from")) if plan.get("inherited_from") else None,
    )


def _tv_episode_plan_value(evidence: Mapping[str, Any], key: str) -> Any:
    plan = tv_episode_plan_from_evidence(evidence)
    return plan.get(key) if plan is not None else None


def _mutable_tv_episode_plan(evidence: MutableMapping[str, Any]) -> MutableMapping[str, Any] | None:
    plan = evidence.get(TV_EPISODE_PLAN_EVIDENCE_KEY)
    return plan if isinstance(plan, MutableMapping) else None


def _optional_str(value: object) -> str | None:
    return str(value) if value else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]
