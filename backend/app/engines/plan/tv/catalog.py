from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from app.domain.match import MatchResult
from app.domain.tv import TVEpisodeCatalog, episode_catalog_from_mapping, episode_number_value
from app.domain.tv import TVEpisodeFile


class TVEpisodeCatalogProvider(Protocol):
    def tv_episode_catalog(self, *, tmdb_id: int | None) -> TVEpisodeCatalog | Mapping:
        ...

    def tv_episode_titles(self, *, tmdb_id: int | None, season_numbers: Sequence[int]) -> TVEpisodeCatalog | Mapping:
        ...


def catalog_context(catalog: TVEpisodeCatalog) -> str:
    return "" if catalog.is_empty else catalog.to_prompt_text()


def catalog_from_provider(provider: TVEpisodeCatalogProvider, match_result: MatchResult) -> TVEpisodeCatalog:
    if not match_result.tmdb_id:
        return TVEpisodeCatalog.empty()
    return _catalog_from_value(provider.tv_episode_catalog(tmdb_id=match_result.tmdb_id))


def season_scoped_catalog_from_provider(
    provider: TVEpisodeCatalogProvider,
    match_result: MatchResult,
    season_numbers: Sequence[int],
) -> TVEpisodeCatalog:
    seasons = tuple(sorted({int(season) for season in season_numbers if season is not None and int(season) >= 0}))
    if not match_result.tmdb_id or not seasons:
        return TVEpisodeCatalog.empty()
    return _catalog_from_value(
        provider.tv_episode_titles(tmdb_id=match_result.tmdb_id, season_numbers=seasons)
    )


def attach_titles(
    episodes: Sequence[TVEpisodeFile],
    catalog: TVEpisodeCatalog,
    metadata: Mapping[str, object],
) -> None:
    for episode in episodes:
        title = catalog.titles_for_range(
            episode.season_number,
            episode.episode_number,
            episode.end_episode_number,
        )
        if title:
            episode.title = title
            episode.title_source = "tmdb_catalog"
            continue
        metadata_title = episode_title_from_metadata(metadata, episode.season_number, episode.episode_number)
        if metadata_title:
            episode.title = metadata_title
            episode.title_source = "metadata"
        elif not episode.title_source:
            episode.title_source = "none"


def episode_title_from_metadata(metadata: Mapping[str, object], season: int | None, episode: int | None) -> str | None:
    if season is None or episode is None:
        return None
    for key in ("episode_titles", "tmdb_episode_titles"):
        title = episode_title_from_mapping(metadata.get(key), season, episode)
        if title:
            return title
    episodes = metadata.get("episodes")
    if isinstance(episodes, Sequence) and not isinstance(episodes, (str, bytes)):
        for item in episodes:
            if not isinstance(item, Mapping):
                continue
            item_season = item.get("season") if "season" in item else item.get("season_number")
            item_episode = item.get("episode") if "episode" in item else item.get("episode_number")
            if episode_number_value(item_season) == season and episode_number_value(item_episode) == episode:
                title = item.get("title") or item.get("name")
                return str(title) if title else None
    return None


def episode_title_from_mapping(value: object, season: int, episode: int) -> str | None:
    if not isinstance(value, Mapping):
        return None
    season_value = value.get(season) or value.get(str(season))
    if not isinstance(season_value, Mapping):
        return None
    title = season_value.get(episode) or season_value.get(str(episode))
    return str(title) if title else None


def _catalog_from_value(value: TVEpisodeCatalog | Mapping | None) -> TVEpisodeCatalog:
    if isinstance(value, TVEpisodeCatalog):
        return value
    if isinstance(value, Mapping):
        return episode_catalog_from_mapping(value)
    return TVEpisodeCatalog.empty()
