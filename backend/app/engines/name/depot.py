from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.core.error import ConfigurationError
from app.domain.depot import DepotCandidateGroup, depot_candidate_group_key

SYSTEM_MEDIA_ROOT_PATTERN = re.compile(
    r"^(?P<title>.+?)(?: \((?P<year>\d{4})\))?(?: \{tmdb-(?P<tmdb_id>\d+)\})?(?: \[[^\]]+\])?$"
)
YEAR_PATTERN = re.compile(r"\(\d{4}\)")
TMDB_PATTERN = re.compile(r"\{tmdb-\d+\}")

PATH_SPLIT_SYSTEM_MARKER = "system_marker"
PATH_SPLIT_UNGROUPED_ROOT_FILE = "ungrouped_root_file"
PATH_SPLIT_UNGROUPED_ROOT_FOLDER = "ungrouped_root_folder"
PATH_SPLIT_UNKNOWN = "unknown"


@dataclass(frozen=True)
class DepotRelativePathParts:
    depot_relative_path: Path
    organize_prefix: Path
    media_relative_path: Path
    media_root_relative_path: Path | None
    media_root_name: str | None
    confidence: str


def split_depot_relative_path(relative_path: Path | str) -> DepotRelativePathParts:
    path = safe_relative_path(relative_path)
    parts = path.parts
    if not parts:
        return DepotRelativePathParts(
            depot_relative_path=path,
            organize_prefix=Path(),
            media_relative_path=path,
            media_root_relative_path=None,
            media_root_name=None,
            confidence=PATH_SPLIT_UNKNOWN,
        )

    for index, part in enumerate(parts):
        if index == len(parts) - 1 and Path(part).suffix:
            continue
        if is_system_media_root_name(part):
            return _split_at(path, parts, index, part, PATH_SPLIT_SYSTEM_MARKER)

    if len(parts) == 1 and Path(parts[0]).suffix and is_system_media_root_name(_stem_for_direct_file(parts[0])):
        return _split_at(path, parts, 0, _stem_for_direct_file(parts[0]), PATH_SPLIT_SYSTEM_MARKER)

    confidence = PATH_SPLIT_UNGROUPED_ROOT_FILE if len(parts) == 1 else PATH_SPLIT_UNGROUPED_ROOT_FOLDER
    return DepotRelativePathParts(
        depot_relative_path=path,
        organize_prefix=Path(),
        media_relative_path=path,
        media_root_relative_path=Path(parts[0]),
        media_root_name=_stem_for_direct_file(parts[0]) if len(parts) == 1 else parts[0],
        confidence=confidence,
    )


def is_system_media_root_name(name: str) -> bool:
    value = str(name or "").strip()
    if not value:
        return False
    if not TMDB_PATTERN.search(value) and not YEAR_PATTERN.search(value):
        return False
    match = SYSTEM_MEDIA_ROOT_PATTERN.match(value)
    return bool(match and (match.group("tmdb_id") or match.group("year")))


def parse_system_media_root_name(name: str) -> dict[str, int | str | None]:
    match = SYSTEM_MEDIA_ROOT_PATTERN.match(str(name or ""))
    if not match:
        return {}
    if not match.group("tmdb_id") and not match.group("year"):
        return {}
    return {
        "metadata_title": match.group("title"),
        "metadata_year": int(match.group("year")) if match.group("year") else None,
        "metadata_tmdb_id": int(match.group("tmdb_id")) if match.group("tmdb_id") else None,
    }


def group_for_organize_prefix(depot_id: str, organize_prefix: Path | str) -> DepotCandidateGroup | None:
    prefix = safe_relative_path(organize_prefix, allow_empty=True)
    if not prefix.parts:
        return None
    return DepotCandidateGroup(
        key=depot_candidate_group_key(depot_id, prefix),
        organize_prefix=prefix,
        display_name=" / ".join(prefix.parts),
    )


def safe_relative_path(value: Path | str, *, allow_empty: bool = False) -> Path:
    text = _path_text(value)
    if text == "":
        if allow_empty:
            return Path()
        raise ConfigurationError("Relative path is required")
    _reject_unsafe_path_text(text)
    path = Path(text.replace("\\", "/"))
    if path.is_absolute() or path.drive:
        raise ConfigurationError(f"Path must be relative: {value}")
    if ".." in path.parts:
        raise ConfigurationError(f"Path cannot contain '..': {value}")
    return path


def safe_relative_fragment(value: Path | str, *, allow_empty: bool = True) -> Path:
    text = _path_text(value)
    if text == "":
        if allow_empty:
            return Path()
        raise ConfigurationError("Path fragment is required")
    _reject_unsafe_path_text(text)
    path = Path(text.replace("\\", "/"))
    if path.is_absolute() or path.drive:
        raise ConfigurationError(f"Path fragment must be relative: {value}")
    if ".." in path.parts:
        raise ConfigurationError(f"Path fragment cannot contain '..': {value}")
    if any(part == "." for part in path.parts):
        raise ConfigurationError(f"Path fragment cannot contain '.': {value}")
    return path


def join_relative_fragments(*parts: Path | str | None) -> Path:
    result = Path()
    for part in parts:
        if part is None:
            continue
        fragment = safe_relative_fragment(part, allow_empty=True)
        if fragment.parts:
            result = result / fragment
    return result


def _split_at(path: Path, parts: tuple[str, ...], index: int, media_root_name: str, confidence: str) -> DepotRelativePathParts:
    organize_prefix = Path(*parts[:index]) if index else Path()
    media_relative_path = Path(*parts[index:])
    media_root_relative_path = Path(*parts[: index + 1])
    return DepotRelativePathParts(
        depot_relative_path=path,
        organize_prefix=organize_prefix,
        media_relative_path=media_relative_path,
        media_root_relative_path=media_root_relative_path,
        media_root_name=media_root_name,
        confidence=confidence,
    )


def _stem_for_direct_file(value: str) -> str:
    return Path(value).stem if Path(value).suffix else value


def _path_text(value: Path | str) -> str:
    if isinstance(value, Path):
        return "" if not value.parts else value.as_posix()
    return str(value or "").strip()


def _reject_unsafe_path_text(text: str) -> None:
    if "\x00" in text:
        raise ConfigurationError("Path cannot contain NUL bytes")
    normalized = text.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise ConfigurationError(f"Path must be relative: {text}")
    if "//" in normalized:
        raise ConfigurationError(f"Path cannot contain empty segments: {text}")
