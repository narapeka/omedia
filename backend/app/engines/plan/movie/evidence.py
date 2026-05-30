from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from app.engines.plan.movie.planner import MovieOrganizeFile

MOVIE_PLAN_EVIDENCE_KEY = "movie_plan"


def movie_plan_evidence(plan: MovieOrganizeFile) -> dict:
    evidence = {
        "media_kind": plan.media_kind,
        "extension": plan.extension or plan.source_path.suffix,
        "primary_source": plan.primary_source_path.name if plan.primary_source_path else None,
        "ignored_duplicate_subtitles": list(plan.ignored_duplicate_subtitles),
    }
    if plan.part_token:
        evidence["part_token"] = plan.part_token
    return evidence


def movie_plan_from_evidence(evidence: Mapping[str, Any]) -> Mapping[str, Any] | None:
    plan = evidence.get(MOVIE_PLAN_EVIDENCE_KEY)
    return plan if isinstance(plan, Mapping) else None


def movie_plan_media_kind(evidence: Mapping[str, Any]) -> str | None:
    return _optional_str(_movie_plan_value(evidence, "media_kind"))


def movie_plan_primary_source(evidence: Mapping[str, Any]) -> str | None:
    return _optional_str(_movie_plan_value(evidence, "primary_source"))


def movie_plan_part_token(evidence: Mapping[str, Any]) -> str | None:
    return _optional_str(_movie_plan_value(evidence, "part_token"))


def movie_plan_extension(evidence: Mapping[str, Any]) -> str | None:
    return _optional_str(_movie_plan_value(evidence, "extension"))


def movie_plan_tag(evidence: Mapping[str, Any]) -> str | None:
    return _optional_str(_movie_plan_value(evidence, "tag"))


def movie_plan_tag_suffix(evidence: Mapping[str, Any]) -> str | None:
    return _optional_str(_movie_plan_value(evidence, "tag_suffix"))


def movie_plan_ignored_duplicate_subtitles(evidence: Mapping[str, Any]) -> list[str]:
    return _string_list(_movie_plan_value(evidence, "ignored_duplicate_subtitles"))


def set_movie_plan_tag(evidence: MutableMapping[str, Any], raw_tag: str | None, suffix: str | None) -> bool:
    plan = _mutable_movie_plan(evidence)
    if plan is None:
        return False
    if raw_tag:
        plan["tag"] = raw_tag
        plan["tag_suffix"] = suffix
    else:
        plan.pop("tag", None)
        plan.pop("tag_suffix", None)
    return True


def _movie_plan_value(evidence: Mapping[str, Any], key: str) -> Any:
    plan = movie_plan_from_evidence(evidence)
    return plan.get(key) if plan is not None else None


def _mutable_movie_plan(evidence: MutableMapping[str, Any]) -> MutableMapping[str, Any] | None:
    plan = evidence.get(MOVIE_PLAN_EVIDENCE_KEY)
    return plan if isinstance(plan, MutableMapping) else None


def _optional_str(value: object) -> str | None:
    return str(value) if value else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]

