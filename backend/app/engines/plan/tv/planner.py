from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

from app.domain.match import MatchResult
from app.domain.media import MediaCandidate, MediaExtensionPolicy, MediaFile
from app.domain.tv import (
    TVEpisodeCatalog,
    TVEpisodeFile,
    TV_STRUCTURE_MIXED,
    TV_STRUCTURE_SEASON_SUBFOLDERS,
)
from app.engines.plan.subtitle.selection import SubtitleCandidate, select_subtitle_candidates

from app.engines.plan.tv.catalog import (
    TVEpisodeCatalogProvider,
    attach_titles,
    catalog_from_provider,
    season_scoped_catalog_from_provider,
)
from app.engines.plan.tv.source import (
    candidate_episode_files,
    candidate_subtitle_files,
    candidate_video_files,
    direct_files,
    relative_key,
    subfolder_files,
)
from app.engines.plan.tv.resolution import TVEpisodeExtractor
from app.engines.plan.tv.structure import (
    plan_direct_files,
    plan_direct_segment,
    plan_season_subfolder_segment,
    plan_season_subfolders,
)


class TVEpisodePlanner:
    def __init__(
        self,
        *,
        extensions: MediaExtensionPolicy,
        episode_extractor: TVEpisodeExtractor,
        episode_catalog_provider: TVEpisodeCatalogProvider,
        resolution_chunk_size: int = 100,
    ):
        self.extensions = extensions
        self.episode_extractor = episode_extractor
        self.episode_catalog_provider = episode_catalog_provider
        self.resolution_chunk_size = resolution_chunk_size

    def plan(
        self,
        media_candidate: MediaCandidate,
        match_result: MatchResult,
        *,
        include_subtitles: bool = True,
    ) -> list[TVEpisodeFile]:
        needs_resolution = self._needs_episode_resolution(media_candidate, match_result)
        catalog = (
            catalog_from_provider(self.episode_catalog_provider, match_result)
            if needs_resolution
            else TVEpisodeCatalog.empty()
        )
        show_name = match_result.title or media_candidate.display_name
        video_files = candidate_video_files(media_candidate.files, self.extensions)
        structure = media_candidate.structure

        if not needs_resolution:
            planned_videos = plan_episode_files(
                media_candidate,
                extensions=self.extensions,
                include_subtitles=False,
            )
        elif structure == TV_STRUCTURE_SEASON_SUBFOLDERS:
            planned_videos = plan_season_subfolder_segment(
                video_files,
                show_name=show_name,
                catalog=catalog,
                extractor=self.episode_extractor,
                extensions=self.extensions,
                resolution_chunk_size=self.resolution_chunk_size,
            )
        elif structure == TV_STRUCTURE_MIXED:
            planned_videos = [
                *plan_direct_segment(
                    direct_files(video_files),
                    media_candidate.candidate_path.name,
                    show_name=show_name,
                    catalog=catalog,
                    extractor=self.episode_extractor,
                    extensions=self.extensions,
                    resolution_chunk_size=self.resolution_chunk_size,
                ),
                *plan_season_subfolder_segment(
                    subfolder_files(video_files),
                    show_name=show_name,
                    catalog=catalog,
                    extractor=self.episode_extractor,
                    extensions=self.extensions,
                    resolution_chunk_size=self.resolution_chunk_size,
                ),
            ]
        else:
            planned_videos = plan_direct_segment(
                video_files,
                media_candidate.candidate_path.name,
                show_name=show_name,
                catalog=catalog,
                extractor=self.episode_extractor,
                extensions=self.extensions,
                resolution_chunk_size=self.resolution_chunk_size,
            )

        planned: list[TVEpisodeFile] = list(planned_videos)
        if include_subtitles:
            planned.extend(
                plan_subtitles(
                    media_candidate,
                    planned_videos,
                    extensions=self.extensions,
                    parser_only_planner=lambda item: plan_episode_files(
                        item,
                        extensions=self.extensions,
                        include_subtitles=True,
                    ),
                )
            )
        title_catalog = catalog
        if title_catalog.is_empty:
            title_catalog = season_scoped_catalog_from_provider(
                self.episode_catalog_provider,
                match_result,
                _planned_seasons(planned),
            )
        attach_titles(planned, title_catalog, match_result.metadata)
        return deduplicate_subtitles(
            sorted(planned, key=lambda item: relative_key(media_candidate.files, item.source_path).lower()),
            media_candidate.files,
        )

    def _needs_episode_resolution(
        self,
        media_candidate: MediaCandidate,
        match_result: MatchResult,
    ) -> bool:
        if not match_result.is_high_confidence:
            return False
        planned = plan_episode_files(
            media_candidate,
            extensions=self.extensions,
            include_subtitles=False,
        )
        video_count = len(candidate_video_files(media_candidate.files, self.extensions))
        return len(planned) < video_count or any(not item.confident for item in planned)


def plan_episode_files(
    media_candidate: MediaCandidate,
    *,
    extensions: MediaExtensionPolicy,
    include_subtitles: bool = False,
) -> list[TVEpisodeFile]:
    files = candidate_episode_files(media_candidate.files, extensions, include_subtitles=include_subtitles)
    structure = media_candidate.structure
    if structure == TV_STRUCTURE_SEASON_SUBFOLDERS:
        planned = plan_season_subfolders(files, extensions)
    elif structure == TV_STRUCTURE_MIXED:
        planned = [
            *plan_direct_files(direct_files(files), media_candidate.candidate_path.name, extensions),
            *plan_season_subfolders(subfolder_files(files), extensions),
        ]
    else:
        planned = plan_direct_files(files, media_candidate.candidate_path.name, extensions)
    return deduplicate_subtitles(
        sorted(planned, key=lambda item: relative_key(media_candidate.files, item.source_path).lower()),
        media_candidate.files,
    )


def _planned_seasons(planned: list[TVEpisodeFile]) -> tuple[int, ...]:
    return tuple(
        sorted(
            {
                int(item.season_number)
                for item in planned
                if item.season_number is not None and int(item.season_number) >= 0
            }
        )
    )


def plan_subtitles(
    media_candidate: MediaCandidate,
    planned_videos: Sequence[TVEpisodeFile],
    *,
    extensions: MediaExtensionPolicy,
    parser_only_planner: Callable[[MediaCandidate], list[TVEpisodeFile]],
) -> list[TVEpisodeFile]:
    subtitle_files = candidate_subtitle_files(media_candidate.files, extensions)
    if not subtitle_files:
        return []

    planned: list[TVEpisodeFile] = []
    inherited_paths: set[Path] = set()
    for file in subtitle_files:
        related = related_video_plan(file, media_candidate.files, planned_videos)
        if related is None:
            continue
        inherited_paths.add(file.path)
        planned.append(
            TVEpisodeFile(
                source_path=file.path,
                season_number=related.season_number,
                episode_number=related.episode_number,
                end_episode_number=related.end_episode_number,
                extension=file.path.suffix,
                title=related.title,
                title_source=related.title_source,
                is_sidecar=True,
                media_kind="subtitle",
                confident=related.confident,
                resolution_status=related.resolution_status,
                resolution_key=related.resolution_key,
                parser_result=dict(related.parser_result or {}),
                llm_result=dict(related.llm_result or {}) if related.llm_result else None,
                resolution_warning=related.resolution_warning,
                resolution_requested_keys=list(related.resolution_requested_keys),
                resolution_applied_keys=list(related.resolution_applied_keys),
                resolution_junk_keys=list(related.resolution_junk_keys),
                inherited_from=relative_key(media_candidate.files, related.source_path),
            )
        )

    if len(inherited_paths) == len(subtitle_files):
        return planned

    parser_only = parser_only_planner(media_candidate)
    planned.extend(
        episode
        for episode in parser_only
        if episode.media_kind == "subtitle" and episode.source_path not in inherited_paths
    )
    return planned


def deduplicate_subtitles(
    planned: list[TVEpisodeFile],
    files: Iterable[MediaFile],
) -> list[TVEpisodeFile]:
    relative_by_path = {file.path: file.relative_path for file in files}
    subtitle_candidates = [
        SubtitleCandidate(
            value=episode,
            group_key=(
                episode.season_number,
                episode.episode_number,
                episode.end_episode_number,
            ),
            source_path=episode.source_path,
            relative_path=relative_by_path.get(episode.source_path, Path(episode.source_path.name)),
            extension=(episode.extension or episode.source_path.suffix).lower(),
        )
        for episode in planned
        if episode.media_kind == "subtitle"
    ]
    selected_subtitles: dict[Path, TVEpisodeFile] = {}
    for selection in select_subtitle_candidates(subtitle_candidates):
        episode = selection.selected.value
        episode.ignored_duplicate_subtitles = [
            ignored.relative_path.as_posix()
            for ignored in selection.ignored
        ]
        selected_subtitles[episode.source_path] = episode

    return [
        episode
        for episode in planned
        if episode.media_kind != "subtitle" or episode.source_path in selected_subtitles
    ]


def related_video_plan(
    subtitle: MediaFile,
    files: Iterable[MediaFile],
    planned_videos: Sequence[TVEpisodeFile],
) -> TVEpisodeFile | None:
    relative_by_path = {file.path: file.relative_path for file in files}
    subtitle_parent = subtitle.relative_path.parent
    subtitle_stem = subtitle.path.stem.casefold()
    for video in planned_videos:
        video_relative = relative_by_path.get(video.source_path, Path(video.source_path.name))
        if video_relative.parent != subtitle_parent:
            continue
        video_stem = video.source_path.stem.casefold()
        if subtitle_stem == video_stem or subtitle_stem.startswith(f"{video_stem}."):
            return video
    return None
