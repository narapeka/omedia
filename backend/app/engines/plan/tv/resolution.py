from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Protocol

from app.domain.tv import EpisodeLLMResult, TVEpisodeCatalog, TVEpisodeFile
from .parser import TVEpisodeParse, TVParseConfidence


class TVResolutionStatus(str, Enum):
    NOT_NEEDED = "not_needed"
    ATTEMPTED = "attempted"
    APPLIED = "applied"
    ERROR = "error"


@dataclass(frozen=True)
class TVResolutionResult:
    parser_results: dict[str, TVEpisodeParse]
    merged_results: dict[str, TVEpisodeParse]
    llm_results: dict[str, EpisodeLLMResult]
    requested_keys: list[str] = field(default_factory=list)
    applied_keys: list[str] = field(default_factory=list)
    junk_keys: list[str] = field(default_factory=list)
    status: TVResolutionStatus = TVResolutionStatus.NOT_NEEDED
    warning: str | None = None


class TVEpisodeExtractor(Protocol):
    def extract_episodes(
        self,
        *,
        show_name: str,
        filenames: Sequence[str],
        tmdb_context: str = "",
        chunk_size: int = 100,
    ) -> dict[str, EpisodeLLMResult]:
        ...


def resolve_tv_episode_segment(
    parser_results: Mapping[str, TVEpisodeParse],
    *,
    request_keys: Sequence[str],
    show_name: str,
    tmdb_context: str,
    catalog: TVEpisodeCatalog,
    extractor: TVEpisodeExtractor,
    chunk_size: int = 100,
) -> TVResolutionResult:
    parser_map = {key: parser_results[key] for key in request_keys if key in parser_results}
    if not any(value.needs_resolution for value in parser_map.values()):
        return _result(parser_map, TVResolutionStatus.NOT_NEEDED)

    keys = [key for key in request_keys if parser_map.get(key) and parser_map[key].needs_resolution]
    try:
        raw_results = _extract_episode_chunks(
            extractor,
            show_name=show_name,
            keys=keys,
            tmdb_context=tmdb_context,
            chunk_size=chunk_size,
        )
    except Exception as exc:
        return _result(
            parser_map,
            TVResolutionStatus.ERROR,
            requested_keys=keys,
            warning=f"TV resolution failed: {exc}",
        )
    if not isinstance(raw_results, Mapping):
        return _result(
            parser_map,
            TVResolutionStatus.ERROR,
            requested_keys=keys,
            warning="TV resolution returned invalid output",
        )

    allowed = set(keys)
    llm_results: dict[str, EpisodeLLMResult] = {}
    rejected: list[str] = []
    for key, value in raw_results.items():
        if key not in allowed or not isinstance(value, EpisodeLLMResult):
            continue
        rejection = _rejection_reason(value, catalog)
        if rejection:
            rejected.append(f"{key}: {rejection}")
            continue
        llm_results[str(key)] = value

    merged = dict(parser_map)
    applied_keys: list[str] = []
    junk_keys: list[str] = []
    for key, value in llm_results.items():
        if value.season == -1 or value.episode == -1:
            junk_keys.append(key)
            continue
        original = merged[key]
        merged_value = _merge_llm_result(original, value)
        merged[key] = merged_value
        if merged_value != original:
            applied_keys.append(key)

    status = TVResolutionStatus.APPLIED if applied_keys or junk_keys else TVResolutionStatus.ATTEMPTED
    warning = None
    if not llm_results:
        warning = "TV resolution returned no matching results"
    if rejected:
        warning = "; ".join(rejected) if warning is None else f"{warning}; {'; '.join(rejected)}"
    return TVResolutionResult(
        parser_results=parser_map,
        merged_results=merged,
        llm_results=llm_results,
        requested_keys=keys,
        applied_keys=applied_keys,
        junk_keys=junk_keys,
        status=status,
        warning=warning,
    )


def _extract_episode_chunks(
    extractor,
    *,
    show_name: str,
    keys: Sequence[str],
    tmdb_context: str,
    chunk_size: int,
) -> dict[str, EpisodeLLMResult]:
    if chunk_size <= 0:
        raise ValueError("TV resolution chunk size must be greater than zero")
    results: dict[str, EpisodeLLMResult] = {}
    for chunk_start in range(0, len(keys), chunk_size):
        chunk = list(keys[chunk_start:chunk_start + chunk_size])
        raw_chunk = extractor.extract_episodes(
            show_name=show_name,
            filenames=chunk,
            tmdb_context=tmdb_context,
            chunk_size=chunk_size,
        )
        if not isinstance(raw_chunk, Mapping):
            raise TypeError("TV resolution returned invalid output")
        results.update(raw_chunk)
    return results


def _merge_llm_result(parser_result: TVEpisodeParse, llm_result: EpisodeLLMResult) -> TVEpisodeParse:
    if parser_result.is_explicit:
        return parser_result

    season = parser_result.season
    season_confidence = parser_result.season_confidence
    if season_confidence != TVParseConfidence.EXPLICIT:
        season = llm_result.season
        season_confidence = TVParseConfidence.LLM

    episode = parser_result.episode
    episode_confidence = parser_result.episode_confidence
    if episode_confidence != TVParseConfidence.EXPLICIT:
        episode = llm_result.episode
        episode_confidence = TVParseConfidence.LLM

    end_episode = parser_result.end_episode
    range_confidence = parser_result.range_confidence
    if range_confidence != TVParseConfidence.EXPLICIT:
        end_episode = llm_result.end_episode
        range_confidence = TVParseConfidence.LLM if end_episode is not None else TVParseConfidence.NONE

    return replace(
        parser_result,
        season=season,
        episode=episode,
        end_episode=end_episode,
        season_confidence=season_confidence,
        episode_confidence=episode_confidence,
        range_confidence=range_confidence,
        evidence=(*parser_result.evidence, "tv_resolution_llm"),
    )


def with_resolution_evidence(
    episode: TVEpisodeFile,
    key: str,
    resolution: TVResolutionResult,
) -> TVEpisodeFile:
    llm_result = resolution.llm_results.get(key)
    status = "applied" if key in resolution.applied_keys else resolution.status.value
    episode.resolution_status = status
    episode.resolution_key = key
    episode.parser_result = _episode_info_dict(resolution.parser_results.get(key))
    episode.llm_result = _llm_result_dict(llm_result)
    episode.resolution_warning = resolution.warning
    episode.resolution_requested_keys = list(resolution.requested_keys)
    episode.resolution_applied_keys = list(resolution.applied_keys)
    episode.resolution_junk_keys = list(resolution.junk_keys)
    return episode


def _rejection_reason(result: EpisodeLLMResult, catalog: TVEpisodeCatalog) -> str | None:
    if result.season == -1 or result.episode == -1:
        return None
    if result.season < 0:
        return "invalid season"
    if result.episode < 1:
        return "invalid episode"
    if result.end_episode is not None:
        if result.end_episode < result.episode:
            return "invalid episode range"
    if catalog.is_empty:
        return None
    season = catalog.seasons.get(result.season)
    if not season or result.episode not in season:
        return "not present in TMDB catalog"
    if result.end_episode is not None and result.end_episode not in season:
        return "range end not present in TMDB catalog"
    return None


def _episode_info_dict(value: TVEpisodeParse | None) -> dict[str, object] | None:
    return value.as_evidence() if value is not None else None


def _llm_result_dict(value: EpisodeLLMResult | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "season": value.season,
        "episode": value.episode,
        "end_episode": value.end_episode,
    }


def _result(
    parser_results: dict[str, TVEpisodeParse],
    status: TVResolutionStatus,
    *,
    requested_keys: Sequence[str] = (),
    warning: str | None = None,
) -> TVResolutionResult:
    return TVResolutionResult(
        parser_results=dict(parser_results),
        merged_results=dict(parser_results),
        llm_results={},
        requested_keys=list(requested_keys),
        status=status,
        warning=warning,
    )
