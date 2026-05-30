from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.domain.media import MediaCandidate, MediaExtensionPolicy, MediaFile
from app.domain.movie import MovieFileSet
from app.engines.name.movie.part import extract_movie_part_token
from app.engines.plan.subtitle.selection import SubtitleCandidate, select_subtitle_candidates

MOVIE_FOLDER_STRUCTURE = "movie_folder"


@dataclass
class MovieOrganizeFile:
    source_path: Path
    extension: str
    media_kind: str
    primary_source_path: Path | None = None
    part_token: str | None = None
    ignored_duplicate_subtitles: list[str] = field(default_factory=list)


def collect_movie_file_set(
    candidate: MediaCandidate,
    extensions: MediaExtensionPolicy,
) -> MovieFileSet | None:
    video_files = [file.path for file in candidate.files if file.extension.lower() in extensions.video]
    if not video_files:
        return None
    primary = sorted(video_files, key=lambda path: path.name.lower())[0]
    subtitles = sorted(
        [file.path for file in candidate.files if file.extension.lower() in extensions.subtitle],
        key=lambda path: path.name.lower(),
    )
    sidecars = sorted(
        [file.path for file in candidate.files if file.extension.lower() in extensions.sidecar],
        key=lambda path: path.name.lower(),
    )
    return MovieFileSet(primary_file=primary, subtitle_files=subtitles, sidecar_files=sidecars)


def plan_movie_files_for_candidate(
    candidate: MediaCandidate,
    extensions: MediaExtensionPolicy,
) -> list[MovieOrganizeFile]:
    video_files = sorted(
        [file for file in candidate.files if file.extension.lower() in extensions.video],
        key=lambda file: file.relative_path.as_posix().lower(),
    )
    subtitle_files = sorted(
        [file for file in candidate.files if file.extension.lower() in extensions.subtitle],
        key=lambda file: file.relative_path.as_posix().lower(),
    )
    primary_plans = _planned_primary_files(candidate, video_files)
    primary = primary_plans[0].source_path if primary_plans else None
    planned: list[MovieOrganizeFile] = []
    planned.extend(primary_plans)

    subtitle_candidates = [
        SubtitleCandidate(
            value=file,
            group_key=candidate.id,
            source_path=file.path,
            relative_path=file.relative_path,
            extension=file.extension.lower(),
        )
        for file in subtitle_files
    ]
    for selection in select_subtitle_candidates(subtitle_candidates):
        file = selection.selected.value
        planned.append(
            MovieOrganizeFile(
                source_path=file.path,
                extension=file.path.suffix,
                media_kind="subtitle",
                primary_source_path=primary,
                ignored_duplicate_subtitles=[
                    ignored.relative_path.as_posix()
                    for ignored in selection.ignored
                ],
            )
        )
    return planned


def _planned_primary_files(
    candidate: MediaCandidate,
    video_files: list[MediaFile],
) -> list[MovieOrganizeFile]:
    if not video_files:
        return []
    if candidate.structure == MOVIE_FOLDER_STRUCTURE and len(video_files) > 1:
        tokenized = [
            (file, extract_movie_part_token(file.path))
            for file in video_files
        ]
        tokens = [token for _, token in tokenized]
        unique_tokens = {token.casefold() for token in tokens if token}
        if all(tokens) and len(unique_tokens) == len(tokens):
            return [
                MovieOrganizeFile(
                    source_path=file.path,
                    extension=file.path.suffix,
                    media_kind="primary",
                    primary_source_path=file.path,
                    part_token=token,
                )
                for file, token in tokenized
                if token is not None
            ]
    primary = video_files[0].path
    return [
        MovieOrganizeFile(
            source_path=primary,
            extension=primary.suffix,
            media_kind="primary",
            primary_source_path=primary,
        )
    ]

