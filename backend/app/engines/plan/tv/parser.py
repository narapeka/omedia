from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from app.engines.name.tv.pattern import (
    TVPatternMatch,
    find_episode,
    find_range,
    find_season,
    find_season_episode,
    parse_chinese_number,
)
from app.engines.name.tv.source import explicit_folder_season


class TVParseConfidence(str, Enum):
    EXPLICIT = "explicit"
    CONTEXT = "context"
    DEFAULT = "default"
    SEQUENCE = "sequence"
    UNKNOWN = "unknown"
    LLM = "llm"
    NONE = "none"


_RELIABLE_CONFIDENCE = {
    TVParseConfidence.EXPLICIT,
    TVParseConfidence.CONTEXT,
    TVParseConfidence.LLM,
}


@dataclass(frozen=True)
class TVEpisodeParse:
    season: int | None
    episode: int | None
    end_episode: int | None
    season_confidence: TVParseConfidence
    episode_confidence: TVParseConfidence
    range_confidence: TVParseConfidence = TVParseConfidence.NONE
    evidence: tuple[str, ...] = ()
    warning: str | None = None

    @property
    def is_resolved(self) -> bool:
        return (
            self.season is not None
            and self.episode is not None
            and self.season_confidence in _RELIABLE_CONFIDENCE
            and self.episode_confidence in _RELIABLE_CONFIDENCE
            and self.range_confidence != TVParseConfidence.UNKNOWN
        )

    @property
    def is_explicit(self) -> bool:
        return (
            self.season_confidence == TVParseConfidence.EXPLICIT
            and self.episode_confidence == TVParseConfidence.EXPLICIT
            and self.range_confidence in {TVParseConfidence.EXPLICIT, TVParseConfidence.NONE}
        )

    @property
    def needs_resolution(self) -> bool:
        return not self.is_resolved

    def with_context_season(self, season: int, *, evidence: str) -> "TVEpisodeParse":
        if self.season_confidence in {TVParseConfidence.EXPLICIT, TVParseConfidence.LLM}:
            return self
        return replace(
            self,
            season=season,
            season_confidence=TVParseConfidence.CONTEXT,
            evidence=(*self.evidence, evidence),
        )

    def with_default_season(self, season: int = 1, *, evidence: str = "default_season") -> "TVEpisodeParse":
        if self.season_confidence in _RELIABLE_CONFIDENCE:
            return self
        return replace(
            self,
            season=season,
            season_confidence=TVParseConfidence.DEFAULT,
            evidence=(*self.evidence, evidence),
        )

    def as_evidence(self) -> dict[str, object]:
        return {
            "season": self.season,
            "episode": self.episode,
            "end_episode": self.end_episode,
            "season_confidence": self.season_confidence.value,
            "episode_confidence": self.episode_confidence.value,
            "range_confidence": self.range_confidence.value,
            "needs_resolution": self.needs_resolution,
            "evidence": list(self.evidence),
            "warning": self.warning,
        }


def extract_episode_info(filename: str, position: int = 1) -> TVEpisodeParse:
    range_match = find_range(filename)
    if range_match is not None:
        return _parse_from_range(range_match)

    season_episode = find_season_episode(filename)
    if season_episode is not None:
        return TVEpisodeParse(
            season=season_episode.season,
            episode=season_episode.episode,
            end_episode=None,
            season_confidence=TVParseConfidence.EXPLICIT,
            episode_confidence=TVParseConfidence.EXPLICIT,
            evidence=(f"pattern:{season_episode.token}",),
        )

    episode = find_episode(filename)
    if episode is not None:
        return TVEpisodeParse(
            season=1,
            episode=episode.episode,
            end_episode=None,
            season_confidence=TVParseConfidence.DEFAULT,
            episode_confidence=TVParseConfidence.EXPLICIT,
            evidence=(f"pattern:{episode.token}", "default_season"),
        )

    season = find_season(filename)
    if season is not None:
        return TVEpisodeParse(
            season=season.season,
            episode=position,
            end_episode=None,
            season_confidence=TVParseConfidence.EXPLICIT,
            episode_confidence=TVParseConfidence.SEQUENCE,
            evidence=(f"pattern:{season.token}", "sequence_episode"),
        )

    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    stripped = stem.strip()
    if stripped.isdigit() and int(stripped) >= 1:
        return TVEpisodeParse(
            season=1,
            episode=int(stripped),
            end_episode=None,
            season_confidence=TVParseConfidence.DEFAULT,
            episode_confidence=TVParseConfidence.SEQUENCE,
            evidence=("numeric_stem", "default_season"),
        )

    return TVEpisodeParse(
        season=1,
        episode=position,
        end_episode=None,
        season_confidence=TVParseConfidence.DEFAULT,
        episode_confidence=TVParseConfidence.SEQUENCE,
        evidence=("sequence_episode", "default_season"),
    )


def apply_folder_context(parse: TVEpisodeParse, folder_name: str) -> TVEpisodeParse:
    season = explicit_folder_season(folder_name)
    if season is not None:
        return parse.with_context_season(season, evidence=f"folder_season:{folder_name}")
    return parse.with_default_season()


def _parse_from_range(match: TVPatternMatch) -> TVEpisodeParse:
    season_confidence = TVParseConfidence.EXPLICIT if match.season is not None else TVParseConfidence.DEFAULT
    evidence = (f"pattern:{match.token}",)
    if match.season is None:
        evidence = (*evidence, "default_season")
    return TVEpisodeParse(
        season=match.season if match.season is not None else 1,
        episode=match.episode,
        end_episode=match.end_episode,
        season_confidence=season_confidence,
        episode_confidence=TVParseConfidence.EXPLICIT,
        range_confidence=TVParseConfidence.EXPLICIT,
        evidence=evidence,
    )
