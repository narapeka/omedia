from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

TV_STRUCTURE_DIRECT_FILES = "direct_files"
TV_STRUCTURE_SEASON_SUBFOLDERS = "season_subfolders"
TV_STRUCTURE_MIXED = "mixed"
TV_STRUCTURE_EMPTY = "empty"


@dataclass(frozen=True)
class TVTagSuffix:
    raw_tag: str
    rendered_suffix: str


@dataclass
class TVEpisodeFile:
    source_path: Path
    season_number: int
    episode_number: int
    end_episode_number: int | None = None
    extension: str | None = None
    title: str | None = None
    title_source: str | None = None
    is_sidecar: bool = False
    media_kind: str = "video"
    confident: bool = False
    ignored_duplicate_subtitles: list[str] = field(default_factory=list)
    resolution_status: str = "not_needed"
    resolution_key: str | None = None
    parser_result: dict[str, Any] | None = None
    llm_result: dict[str, Any] | None = None
    resolution_warning: str | None = None
    resolution_requested_keys: list[str] = field(default_factory=list)
    resolution_applied_keys: list[str] = field(default_factory=list)
    resolution_junk_keys: list[str] = field(default_factory=list)
    inherited_from: str | None = None


@dataclass
class TVShowIdentity:
    source_name: str
    title: str | None = None
    original_title: str | None = None
    year: int | None = None
    tmdb_id: int | None = None
    tag: TVTagSuffix | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TVEpisodeCatalog:
    seasons: dict[int, dict[int, str]] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "TVEpisodeCatalog":
        return cls()

    @property
    def is_empty(self) -> bool:
        return not any(self.seasons.values())

    def title(self, season: int, episode: int) -> str | None:
        value = self.seasons.get(int(season), {}).get(int(episode))
        return str(value) if value else None

    def titles_for_range(self, season: int, episode: int, end_episode: int | None) -> str | None:
        if end_episode is None:
            return self.title(season, episode)
        end = int(end_episode)
        start = int(episode)
        numbers = [start]
        if end != start:
            numbers.append(end)
        titles = [
            title
            for number in numbers
            for title in [self.title(season, number)]
            if title
        ]
        return "-".join(titles) if titles else None

    def to_prompt_text(self) -> str:
        return format_episode_catalog_for_prompt(self)


def episode_catalog_from_mapping(value: Mapping[int | str, Mapping[int | str, object]] | None) -> TVEpisodeCatalog:
    seasons: dict[int, dict[int, str]] = {}
    for raw_season, raw_episodes in (value or {}).items():
        if not isinstance(raw_episodes, Mapping):
            continue
        season = episode_number_value(raw_season)
        if season is None:
            continue
        titles: dict[int, str] = {}
        for raw_episode, raw_title in raw_episodes.items():
            if not raw_title:
                continue
            episode = episode_number_value(raw_episode)
            if episode is None:
                continue
            titles[episode] = str(raw_title)
        if titles:
            seasons[season] = dict(sorted(titles.items()))
    return TVEpisodeCatalog(dict(sorted(seasons.items())))


def episode_number_value(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def format_episode_catalog_for_prompt(catalog: TVEpisodeCatalog) -> str:
    lines = ["Official TMDB Episode List:"]
    for season_number in sorted(catalog.seasons):
        episodes = catalog.seasons[season_number]
        if not episodes:
            continue
        lines.append(f"Season {season_number}:")
        for episode_number in sorted(episodes):
            lines.append(f"  - Episode {episode_number}: {episodes[episode_number]}")
    return "\n".join(lines)


@dataclass(frozen=True)
class EpisodeLLMResult:
    filename: str
    season: int
    episode: int
    end_episode: int | None = None
