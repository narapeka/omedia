from __future__ import annotations

from pathlib import Path

from app.core.path import normalized_path_key, safe_relative_to
from app.domain.media import MediaType
from app.domain.origin import UNKNOWN_FOLDER_NAME, Origin
from app.domain.media import MediaExtensionPolicy

from app.engines.scan.media import (
    has_eligible_video,
    is_path_size_eligible_non_subtitle,
    is_size_eligible_non_subtitle,
    source_inventory_files_under,
)
from app.engines.scan.source import movie_file_candidate, scan_origin_candidate
from app.engines.scan.types import WatchSourcePackage

def resolve_watch_candidate_path(
    origin: Origin,
    event_path: Path,
    extensions: MediaExtensionPolicy,
    *,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> Path | None:
    """Map a filesystem event path to the current media candidate boundary."""
    relative = safe_relative_to(event_path, origin.path)
    if relative is None or not relative.parts:
        return None
    if any(part.casefold() == UNKNOWN_FOLDER_NAME for part in relative.parts):
        return None

    candidate_path = origin.path / relative.parts[0]
    if origin.media_type == MediaType.MOVIE:
        if len(relative.parts) == 1 and candidate_path.is_file():
            return candidate_path if movie_file_candidate(
                origin.path,
                candidate_path,
                extensions,
                min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
            ) is not None else None
        if candidate_path.is_dir() and scan_origin_candidate(
            origin,
            candidate_path,
            extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        ) is not None:
            return candidate_path
        return None

    if origin.media_type == MediaType.TV:
        if not candidate_path.is_dir():
            return None
        return candidate_path if scan_origin_candidate(
            origin,
            candidate_path,
            extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        ) is not None else None

    return None

def resolve_watch_source_package(
    origin: Origin,
    event_path: Path,
    extensions: MediaExtensionPolicy,
    *,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> WatchSourcePackage | None:
    relative = safe_relative_to(event_path, origin.path)
    if relative is None or not relative.parts:
        return None
    if any(part.casefold() == UNKNOWN_FOLDER_NAME for part in relative.parts):
        return None
    package_path = origin.path / relative.parts[0]

    candidate = scan_origin_candidate(
        origin,
        package_path,
        extensions,
        min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
    )
    if candidate is not None:
        return WatchSourcePackage(path=candidate.candidate_path)

    reason = _rejected_watch_source_package_reason(
        origin,
        package_path,
        extensions,
        min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
    )
    if reason is None:
        return None
    return WatchSourcePackage(path=package_path, rejected_reason=reason)

def scan_watch_source_packages(
    origin: Origin,
    extensions: MediaExtensionPolicy,
    *,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> list[WatchSourcePackage]:
    if not origin.path.exists() or not origin.path.is_dir():
        return []
    packages: list[WatchSourcePackage] = []
    for child in sorted(origin.path.iterdir(), key=lambda path: path.name.casefold()):
        if child.name.casefold() == UNKNOWN_FOLDER_NAME:
            continue
        candidate = scan_origin_candidate(
            origin,
            child,
            extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )
        if candidate is not None:
            packages.append(WatchSourcePackage(path=candidate.candidate_path))
            continue
        reason = _rejected_watch_source_package_reason(
            origin,
            child,
            extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )
        if reason is not None:
            packages.append(WatchSourcePackage(path=child, rejected_reason=reason))
    return packages

def _rejected_watch_source_package_reason(
    origin: Origin,
    package_path: Path,
    extensions: MediaExtensionPolicy,
    *,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> str | None:
    if (
        not package_path.exists()
        or normalized_path_key(package_path.parent) != normalized_path_key(origin.path)
        or package_path.name.casefold() == UNKNOWN_FOLDER_NAME
    ):
        return None
    if package_path.is_file():
        if origin.media_type != MediaType.MOVIE:
            return None
        extension = package_path.suffix.lower()
        if extension not in extensions.video:
            return None
        if not is_path_size_eligible_non_subtitle(
            package_path,
            extensions=extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        ):
            return "below_min_non_subtitle_file_size"
        return None
    if not package_path.is_dir():
        return None
    files = source_inventory_files_under(
        package_path,
        recursive=True,
        extensions=extensions,
        excluded_dir_names={UNKNOWN_FOLDER_NAME},
    )
    if not files:
        return None
    eligible_files = [
        file
        for file in files
        if is_size_eligible_non_subtitle(
            file,
            extensions=extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )
    ]
    if has_eligible_video(eligible_files, extensions):
        return None
    video_files = [file for file in files if file.extension.lower() in extensions.video]
    if video_files and any(
        not is_size_eligible_non_subtitle(
            file,
            extensions=extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )
        for file in video_files
    ):
        return "below_min_non_subtitle_file_size"
    if all(file.extension.lower() in extensions.sidecar_like for file in files):
        return "sidecar_only"
    if all(file.extension.lower() not in extensions.supported for file in files):
        return "unsupported_only"
    return "no_eligible_video"
