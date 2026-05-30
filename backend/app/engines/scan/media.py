from __future__ import annotations

import hashlib
from pathlib import Path

from app.domain.media import MediaExtensionPolicy, MediaFile

def is_supported_media_file(path: Path, extensions: MediaExtensionPolicy) -> bool:
    return path.is_file() and path.suffix.lower() in extensions.supported

def is_video_file(path: Path, extensions: MediaExtensionPolicy) -> bool:
    return path.is_file() and path.suffix.lower() in extensions.video

def is_organizable_media_file(path: Path, extensions: MediaExtensionPolicy) -> bool:
    return path.is_file() and path.suffix.lower() in (extensions.video | extensions.subtitle)

def is_sidecar_file(path: Path, extensions: MediaExtensionPolicy) -> bool:
    return path.is_file() and path.suffix.lower() in extensions.sidecar_like

def is_size_eligible_non_subtitle(
    file: MediaFile,
    *,
    extensions: MediaExtensionPolicy,
    min_non_subtitle_file_size_bytes: int | None,
) -> bool:
    if not min_non_subtitle_file_size_bytes:
        return True
    if file.extension.lower() in extensions.subtitle:
        return True
    if file.size_bytes is None:
        return True
    return file.size_bytes >= min_non_subtitle_file_size_bytes

def is_path_size_eligible_non_subtitle(
    path: Path,
    *,
    extensions: MediaExtensionPolicy,
    min_non_subtitle_file_size_bytes: int | None,
) -> bool:
    if not min_non_subtitle_file_size_bytes:
        return True
    if path.suffix.lower() in extensions.subtitle:
        return True
    try:
        size_bytes = path.stat().st_size
    except OSError:
        return True
    return size_bytes >= min_non_subtitle_file_size_bytes

def media_files_under(
    root: Path,
    *,
    recursive: bool,
    extensions: MediaExtensionPolicy,
    excluded_dir_names: set[str] | frozenset[str] | None = None,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> list[MediaFile]:
    if not root.exists() or not root.is_dir():
        return []
    excluded = {name.casefold() for name in excluded_dir_names or set()}
    iterator = root.rglob("*") if recursive else root.iterdir()
    files = []
    for path in iterator:
        if excluded and _has_excluded_relative_part(path, root, excluded):
            continue
        if is_supported_media_file(path, extensions):
            file = to_media_file(path, root, extensions)
            if is_size_eligible_non_subtitle(
                file,
                extensions=extensions,
                min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
            ):
                files.append(file)
    return sorted(files, key=lambda item: item.relative_path.as_posix().lower())

def source_inventory_files_under(
    root: Path,
    *,
    recursive: bool,
    extensions: MediaExtensionPolicy,
    excluded_dir_names: set[str] | frozenset[str] | None = None,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> list[MediaFile]:
    if not root.exists():
        return []
    if root.is_file():
        file = to_media_file(root, root.parent, extensions)
        return [file] if is_size_eligible_non_subtitle(
            file,
            extensions=extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        ) else []
    if not root.is_dir():
        return []
    excluded = {name.casefold() for name in excluded_dir_names or set()}
    iterator = root.rglob("*") if recursive else root.iterdir()
    files: list[MediaFile] = []
    for path in iterator:
        if excluded and _has_excluded_relative_part(path, root, excluded):
            continue
        if path.is_file():
            file = to_media_file(path, root, extensions)
            if is_size_eligible_non_subtitle(
                file,
                extensions=extensions,
                min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
            ):
                files.append(file)
    return sorted(files, key=lambda item: item.relative_path.as_posix().lower())

def fingerprint_candidate(candidate_path: Path, files: list[MediaFile]) -> str:
    digest = hashlib.sha256()
    digest.update(str(candidate_path.resolve()).encode("utf-8", errors="ignore"))
    for file in sorted(files, key=lambda item: item.relative_path.as_posix().lower()):
        digest.update(file.relative_path.as_posix().lower().encode("utf-8", errors="ignore"))
        digest.update(str(file.size_bytes or 0).encode("ascii"))
        digest.update(str(int(file.modified_time or 0)).encode("ascii"))
    return digest.hexdigest()

def has_eligible_video(files: list[MediaFile], extensions: MediaExtensionPolicy) -> bool:
    return any(file.extension.lower() in extensions.video for file in files)


def is_eligible_video_path(
    path: Path,
    extensions: MediaExtensionPolicy,
    *,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> bool:
    return (
        is_video_file(path, extensions)
        and is_path_size_eligible_non_subtitle(
            path,
            extensions=extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )
    )

def to_media_file(path: Path, root: Path, extensions: MediaExtensionPolicy) -> MediaFile:
    stat = path.stat()
    return MediaFile(
        path=path,
        relative_path=path.relative_to(root),
        extension=path.suffix.lower(),
        size_bytes=stat.st_size,
        modified_time=stat.st_mtime,
        is_sidecar=is_sidecar_file(path, extensions),
    )

def _has_excluded_relative_part(path: Path, root: Path, excluded: set[str]) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    return any(part.casefold() in excluded for part in parts)

