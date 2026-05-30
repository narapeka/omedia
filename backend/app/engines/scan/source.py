from __future__ import annotations

from pathlib import Path

from app.core.path import normalized_path_key, safe_relative_to
from app.domain.media import MediaType
from app.domain.origin import UNKNOWN_FOLDER_NAME, Origin
from app.domain.media import MediaCandidate, MediaExtensionPolicy
from app.domain.tv import (
    TV_STRUCTURE_DIRECT_FILES,
    TV_STRUCTURE_EMPTY,
    TV_STRUCTURE_MIXED,
    TV_STRUCTURE_SEASON_SUBFOLDERS,
)

from app.engines.scan.media import (
    fingerprint_candidate,
    has_eligible_video,
    is_eligible_video_path,
    is_size_eligible_non_subtitle,
    media_files_under,
    source_inventory_files_under,
    to_media_file,
)
from app.engines.scan.types import (
    AdHocSourceScan,
    OriginSummaryScan,
)

def scan_tv_root(
    source_root: Path,
    extensions: MediaExtensionPolicy,
    *,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> list[MediaCandidate]:
    if not source_root.exists() or not source_root.is_dir():
        return []
    candidates = []
    for child in sorted((p for p in source_root.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
        if child.name.casefold() == UNKNOWN_FOLDER_NAME:
            continue
        candidate = _tv_folder_candidate(
            source_root,
            child,
            extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates

def detect_tv_structure(
    show_folder: Path,
    extensions: MediaExtensionPolicy,
    *,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> str:
    direct_files = [
        path
        for path in show_folder.iterdir()
        if is_eligible_video_path(
            path,
            extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )
    ] if show_folder.exists() else []
    subdirs = [
        path
        for path in show_folder.iterdir()
        if path.is_dir() and path.name.casefold() != UNKNOWN_FOLDER_NAME
    ] if show_folder.exists() else []
    media_subdirs = [
        path
        for path in subdirs
        if has_eligible_video(
            media_files_under(
                path,
                recursive=False,
                extensions=extensions,
                min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
            ),
            extensions,
        )
    ]
    if direct_files and media_subdirs:
        return TV_STRUCTURE_MIXED
    if media_subdirs:
        return TV_STRUCTURE_SEASON_SUBFOLDERS
    if direct_files:
        return TV_STRUCTURE_DIRECT_FILES
    return TV_STRUCTURE_EMPTY

def scan_movie_root(
    source_root: Path,
    extensions: MediaExtensionPolicy,
    *,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> list[MediaCandidate]:
    if not source_root.exists() or not source_root.is_dir():
        return []
    candidates = []
    for child in sorted(source_root.iterdir(), key=lambda p: p.name.lower()):
        if child.name.casefold() == UNKNOWN_FOLDER_NAME:
            continue
        candidate = movie_file_candidate(
            source_root,
            child,
            extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        ) if child.is_file() else None
        if candidate is None and child.is_dir():
            candidate = _movie_folder_candidate(
                source_root,
                child,
                extensions,
                min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
            )
        if candidate is not None:
            candidates.append(candidate)
    return candidates

def scan_origin(
    origin: Origin,
    extensions: MediaExtensionPolicy,
    *,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> list[MediaCandidate]:
    return scan_source_root(
        origin.path,
        origin.media_type,
        extensions=extensions,
        min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
    )

def scan_origin_candidate(
    origin: Origin,
    candidate_path: Path,
    extensions: MediaExtensionPolicy,
    *,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> MediaCandidate | None:
    relative = safe_relative_to(candidate_path, origin.path)
    if relative is None or not relative.parts or len(relative.parts) != 1:
        return None
    if any(part.casefold() == UNKNOWN_FOLDER_NAME for part in relative.parts):
        return None

    path = origin.path / relative.parts[0]
    if origin.media_type == MediaType.TV:
        return _tv_folder_candidate(
            origin.path,
            path,
            extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )
    if origin.media_type == MediaType.MOVIE:
        if path.is_file():
            return movie_file_candidate(
                origin.path,
                path,
                extensions,
                min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
            )
        if path.is_dir():
            return _movie_folder_candidate(
                origin.path,
                path,
                extensions,
                min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
            )
    return None

def scan_origin_candidates(
    origin: Origin,
    candidate_paths: list[Path],
    extensions: MediaExtensionPolicy,
    *,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> list[MediaCandidate]:
    candidates: list[MediaCandidate] = []
    seen: set[str] = set()
    for path in candidate_paths:
        key = normalized_path_key(path)
        if key in seen:
            continue
        seen.add(key)
        candidate = scan_origin_candidate(
            origin,
            path,
            extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates

def scan_ad_hoc_source(
    source_root: Path,
    media_type: MediaType,
    *,
    extensions: MediaExtensionPolicy,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> list[MediaCandidate]:
    return scan_source_root(
        source_root,
        media_type,
        extensions=extensions,
        min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
    )

def scan_source_root(
    source_root: Path,
    media_type: MediaType,
    *,
    extensions: MediaExtensionPolicy,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> list[MediaCandidate]:
    if media_type == MediaType.TV:
        return scan_tv_root(
            source_root,
            extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )
    if media_type == MediaType.MOVIE:
        return scan_movie_root(
            source_root,
            extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )
    return []

def scan_origin_summary(
    origin: Origin,
    extensions: MediaExtensionPolicy,
    *,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> OriginSummaryScan:
    candidates = scan_origin(
        origin,
        extensions,
        min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
    )
    file_count = sum(len(candidate.files) for candidate in candidates)
    unknown_count = len(media_files_under(origin.path / UNKNOWN_FOLDER_NAME, recursive=True, extensions=extensions))
    return OriginSummaryScan(
        origin_id=origin.id,
        path=origin.path,
        media_type=origin.media_type,
        candidate_count=len(candidates),
        file_count=file_count,
        unknown_count=unknown_count,
    )

def scan_ad_hoc_source_summary(
    source_root: Path,
    media_type: MediaType,
    *,
    extensions: MediaExtensionPolicy,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> AdHocSourceScan:
    candidates = scan_ad_hoc_source(
        source_root,
        media_type,
        extensions=extensions,
        min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
    )
    return AdHocSourceScan(
        path=source_root,
        media_type=media_type,
        candidate_count=len(candidates),
        file_count=sum(len(candidate.files) for candidate in candidates),
        candidates=candidates,
    )

def _tv_folder_candidate(
    source_root: Path,
    show_folder: Path,
    extensions: MediaExtensionPolicy,
    *,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> MediaCandidate | None:
    if (
        not show_folder.exists()
        or not show_folder.is_dir()
        or normalized_path_key(show_folder.parent) != normalized_path_key(source_root)
    ):
        return None
    if show_folder.name.casefold() == UNKNOWN_FOLDER_NAME:
        return None
    files = source_inventory_files_under(
        show_folder,
        recursive=True,
        extensions=extensions,
        excluded_dir_names={UNKNOWN_FOLDER_NAME},
        min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
    )
    if not has_eligible_video(files, extensions):
        return None
    candidate = MediaCandidate(
        id=fingerprint_candidate(show_folder, files),
        media_type=MediaType.TV,
        source_root=source_root,
        candidate_path=show_folder,
        display_name=show_folder.name,
        files=files,
        structure=detect_tv_structure(
            show_folder,
            extensions=extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        ),
    )
    candidate.fingerprint = candidate.id
    return candidate

def movie_file_candidate(
    source_root: Path,
    movie_file: Path,
    extensions: MediaExtensionPolicy,
    *,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> MediaCandidate | None:
    if (
        not movie_file.exists()
        or not movie_file.is_file()
        or normalized_path_key(movie_file.parent) != normalized_path_key(source_root)
    ):
        return None
    if not is_eligible_video_path(
        movie_file,
        extensions,
        min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
    ):
        return None
    files = [to_media_file(movie_file, source_root, extensions)]
    candidate = MediaCandidate(
        id=fingerprint_candidate(movie_file, files),
        media_type=MediaType.MOVIE,
        source_root=source_root,
        candidate_path=movie_file,
        display_name=movie_file.stem,
        files=files,
        structure="standalone_file",
    )
    candidate.fingerprint = candidate.id
    return candidate

def _movie_folder_candidate(
    source_root: Path,
    movie_folder: Path,
    extensions: MediaExtensionPolicy,
    *,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> MediaCandidate | None:
    if (
        not movie_folder.exists()
        or not movie_folder.is_dir()
        or normalized_path_key(movie_folder.parent) != normalized_path_key(source_root)
    ):
        return None
    if movie_folder.name.casefold() == UNKNOWN_FOLDER_NAME:
        return None
    files = source_inventory_files_under(
        movie_folder,
        recursive=True,
        extensions=extensions,
        excluded_dir_names={UNKNOWN_FOLDER_NAME},
        min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
    )
    if not has_eligible_video(files, extensions):
        return None
    candidate = MediaCandidate(
        id=fingerprint_candidate(movie_folder, files),
        media_type=MediaType.MOVIE,
        source_root=source_root,
        candidate_path=movie_folder,
        display_name=movie_folder.name,
        files=files,
        structure="movie_folder",
    )
    candidate.fingerprint = candidate.id
    return candidate
