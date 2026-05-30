from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from app.domain.media import MediaExtensionPolicy, MediaFile
from app.domain.tv import TVEpisodeCatalog, TVEpisodeFile
from app.engines.name.tv.source import (
    explicit_folder_season,
    has_explicit_file_season,
    has_explicit_season_zero,
    valid_season,
)
from app.engines.plan.tv.catalog import catalog_context
from app.engines.plan.tv.parser import (
    TVEpisodeParse,
    TVParseConfidence,
    apply_folder_context,
    extract_episode_info,
)
from app.engines.plan.tv.resolution import (
    TVEpisodeExtractor,
    resolve_tv_episode_segment,
    with_resolution_evidence,
)
from app.engines.plan.tv.source import episode_file, subfolder_files


def plan_direct_segment(
    files: list[MediaFile],
    folder_name: str,
    *,
    show_name: str,
    catalog: TVEpisodeCatalog,
    extractor: TVEpisodeExtractor,
    extensions: MediaExtensionPolicy,
    resolution_chunk_size: int,
) -> list[TVEpisodeFile]:
    if not files:
        return []
    parser_results = _direct_parser_results(files, folder_name)
    keys = [file.path.name for file in files]
    resolution = resolve_tv_episode_segment(
        parser_results,
        request_keys=keys,
        show_name=show_name,
        tmdb_context=catalog_context(catalog),
        catalog=catalog,
        extractor=extractor,
        chunk_size=resolution_chunk_size,
    )

    planned: list[TVEpisodeFile] = []
    for file in files:
        key = file.path.name
        if key in resolution.junk_keys:
            continue
        parse = resolution.merged_results[key]
        if parse.season is None or parse.episode is None:
            continue
        planned.append(
            with_resolution_evidence(
                episode_file(
                    file,
                    season=parse.season,
                    episode=parse.episode,
                    end_episode=parse.end_episode,
                    parse=parse,
                    extensions=extensions,
                ),
                key,
                resolution,
            )
        )
    return planned


def plan_direct_files(
    files: list[MediaFile],
    folder_name: str,
    extensions: MediaExtensionPolicy,
) -> list[TVEpisodeFile]:
    planned: list[TVEpisodeFile] = []
    for file, parse in _direct_file_parses(files, folder_name):
        if parse.season is None or parse.episode is None:
            continue
        planned.append(
            episode_file(
                file,
                season=parse.season,
                episode=parse.episode,
                end_episode=parse.end_episode,
                parse=parse,
                extensions=extensions,
            )
        )
    return planned


def plan_season_subfolder_segment(
    files: list[MediaFile],
    *,
    show_name: str,
    catalog: TVEpisodeCatalog,
    extractor: TVEpisodeExtractor,
    extensions: MediaExtensionPolicy,
    resolution_chunk_size: int,
) -> list[TVEpisodeFile]:
    if not files:
        return []
    groups = season_subfolder_groups(files)
    parsed_by_path = _parse_grouped_files(groups)
    keys_by_path = {file.path: file.relative_path.as_posix() for file in files}
    keys = [keys_by_path[file.path] for file in files]
    resolution = resolve_tv_episode_segment(
        {keys_by_path[file.path]: parsed_by_path[file.path] for file in files},
        request_keys=keys,
        show_name=show_name,
        tmdb_context=catalog_context(catalog),
        catalog=catalog,
        extractor=extractor,
        chunk_size=resolution_chunk_size,
    )

    merged_by_path = {
        file.path: resolution.merged_results[keys_by_path[file.path]]
        for file in files
        if keys_by_path[file.path] not in resolution.junk_keys
    }
    planned: list[TVEpisodeFile] = []
    planned_season_count = 0
    for folder_name, group_files in groups.items():
        non_junk_files = [file for file in group_files if file.path in merged_by_path]
        if not non_junk_files:
            continue
        season = subfolder_season(folder_name, non_junk_files, merged_by_path, planned_season_count + 1)
        planned_season_count += 1
        for file in non_junk_files:
            key = keys_by_path[file.path]
            parse = merged_by_path[file.path].with_context_season(
                season,
                evidence=f"final_subfolder_season:{folder_name}",
            )
            if parse.episode is None:
                continue
            planned.append(
                with_resolution_evidence(
                    episode_file(
                        file,
                        season=season,
                        episode=parse.episode,
                        end_episode=parse.end_episode,
                        parse=parse,
                        extensions=extensions,
                    ),
                    key,
                    resolution,
                )
            )
    return planned


def plan_season_subfolders(
    files: list[MediaFile],
    extensions: MediaExtensionPolicy,
) -> list[TVEpisodeFile]:
    groups = season_subfolder_groups(files)
    parsed = _parse_grouped_files(groups)

    planned: list[TVEpisodeFile] = []
    planned_season_count = 0
    for folder_name, group_files in groups.items():
        season = subfolder_season(folder_name, group_files, parsed, planned_season_count + 1)
        planned_season_count += 1
        for file in group_files:
            parse = parsed[file.path].with_context_season(
                season,
                evidence=f"final_subfolder_season:{folder_name}",
            )
            if parse.episode is None:
                continue
            planned.append(
                episode_file(
                    file,
                    season=season,
                    episode=parse.episode,
                    end_episode=parse.end_episode,
                    parse=parse,
                    extensions=extensions,
                )
            )
    return planned


def season_subfolder_groups(files: list[MediaFile]) -> dict[str, list[MediaFile]]:
    groups: dict[str, list[MediaFile]] = {}
    for file in subfolder_files(files):
        folder_name = file.relative_path.parts[0]
        groups.setdefault(folder_name, []).append(file)
    return {
        folder_name: sorted(groups[folder_name], key=lambda item: item.relative_path.as_posix().lower())
        for folder_name in sorted(groups, key=str.lower)
    }


def subfolder_season(
    folder_name: str,
    files: list[MediaFile],
    parsed: Mapping[Path, TVEpisodeParse],
    fallback_season: int,
) -> int:
    folder_season = explicit_folder_season(folder_name)
    file_seasons = [
        season
        for file in files
        for season in [usable_file_season(file, parsed[file.path])]
        if season is not None
    ]
    if file_seasons:
        unique = set(file_seasons)
        if len(unique) == 1:
            return file_seasons[0]
        if folder_season is not None:
            return folder_season
        return Counter(file_seasons).most_common(1)[0][0]
    if folder_season is not None:
        return folder_season
    return fallback_season


def usable_file_season(
    file: MediaFile,
    parser_result: TVEpisodeParse,
) -> int | None:
    season = valid_season(parser_result.season)
    if season is None:
        return None
    if parser_result.season_confidence not in {TVParseConfidence.EXPLICIT, TVParseConfidence.LLM}:
        return None
    if season == 0:
        return season if has_explicit_season_zero(file.path.name) else None
    if season == 1:
        return season if has_explicit_file_season(file.path.name) else None
    return season


def _direct_parser_results(files: list[MediaFile], folder_name: str) -> dict[str, TVEpisodeParse]:
    return {
        file.path.name: parse
        for file, parse in _direct_file_parses(files, folder_name)
    }


def _direct_file_parses(files: list[MediaFile], folder_name: str) -> list[tuple[MediaFile, TVEpisodeParse]]:
    return [
        (file, apply_folder_context(extract_episode_info(file.path.name, position), folder_name))
        for position, file in enumerate(files, 1)
    ]


def _parse_grouped_files(groups: Mapping[str, list[MediaFile]]) -> dict[Path, TVEpisodeParse]:
    parsed: dict[Path, TVEpisodeParse] = {}
    for folder_name, group_files in groups.items():
        for position, file in enumerate(group_files, 1):
            parsed[file.path] = apply_folder_context(extract_episode_info(file.path.name, position), folder_name)
    return parsed
