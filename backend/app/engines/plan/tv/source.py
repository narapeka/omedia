from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from app.domain.media import MediaExtensionPolicy, MediaFile
from app.domain.tv import TVEpisodeFile
from app.engines.plan.tv.parser import TVEpisodeParse


def candidate_episode_files(
    files: Iterable[MediaFile],
    extensions: MediaExtensionPolicy,
    *,
    include_subtitles: bool,
) -> list[MediaFile]:
    allowed = set(extensions.video)
    if include_subtitles:
        allowed.update(extensions.subtitle)
    return sorted(
        [file for file in files if file.extension.lower() in allowed],
        key=lambda item: item.relative_path.as_posix().lower(),
    )


def candidate_video_files(files: Iterable[MediaFile], extensions: MediaExtensionPolicy) -> list[MediaFile]:
    return sorted(
        [file for file in files if file.extension.lower() in extensions.video],
        key=lambda item: item.relative_path.as_posix().lower(),
    )


def candidate_subtitle_files(files: Iterable[MediaFile], extensions: MediaExtensionPolicy) -> list[MediaFile]:
    return sorted(
        [file for file in files if file.extension.lower() in extensions.subtitle],
        key=lambda item: item.relative_path.as_posix().lower(),
    )


def direct_files(files: Iterable[MediaFile]) -> list[MediaFile]:
    return sorted(
        [file for file in files if len(file.relative_path.parts) == 1],
        key=lambda item: item.relative_path.as_posix().lower(),
    )


def subfolder_files(files: Iterable[MediaFile]) -> list[MediaFile]:
    return sorted(
        [file for file in files if len(file.relative_path.parts) > 1],
        key=lambda item: item.relative_path.as_posix().lower(),
    )


def episode_file(
    file: MediaFile,
    *,
    season: int,
    episode: int,
    end_episode: int | None,
    parse: TVEpisodeParse,
    extensions: MediaExtensionPolicy,
) -> TVEpisodeFile:
    return TVEpisodeFile(
        source_path=file.path,
        season_number=season,
        episode_number=episode,
        end_episode_number=end_episode,
        extension=file.path.suffix,
        is_sidecar=file.path.suffix.lower() in extensions.sidecar_like,
        media_kind="subtitle" if file.path.suffix.lower() in extensions.subtitle else "video",
        confident=parse.is_resolved,
    )


def relative_key(files: Iterable[MediaFile], source_path: Path) -> str:
    for file in files:
        if file.path == source_path:
            return file.relative_path.as_posix()
    return source_path.name
