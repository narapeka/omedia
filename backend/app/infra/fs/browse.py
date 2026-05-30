from __future__ import annotations

import os
import string
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DirectoryEntry:
    name: str
    path: Path
    modified_time: float | None = None
    blocked_reason: str | None = None


@dataclass(frozen=True)
class DirectoryListing:
    path: Path | None
    parent_path: Path | None
    entries: list[DirectoryEntry]
    error: str | None = None


def list_directories(path: Path | None) -> DirectoryListing:
    if path is None or not str(path).strip():
        return DirectoryListing(path=None, parent_path=None, entries=_root_entries())

    directory = path.expanduser()
    if not directory.exists():
        return DirectoryListing(
            path=directory,
            parent_path=_parent_path(directory),
            entries=[],
            error="Directory does not exist",
        )
    if not directory.is_dir():
        return DirectoryListing(
            path=directory,
            parent_path=_parent_path(directory),
            entries=[],
            error="Path is not a directory",
        )

    entries: list[DirectoryEntry] = []
    try:
        children = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
    except OSError as exc:
        return DirectoryListing(path=directory, parent_path=_parent_path(directory), entries=[], error=str(exc))

    for child in children:
        if not child.is_dir():
            continue
        blocked_reason = None
        modified_time = None
        try:
            modified_time = child.stat().st_mtime
        except OSError as exc:
            blocked_reason = type(exc).__name__
        entries.append(
            DirectoryEntry(
                name=child.name,
                path=child,
                modified_time=modified_time,
                blocked_reason=blocked_reason,
            )
        )

    return DirectoryListing(path=directory, parent_path=_parent_path(directory), entries=entries)


def _root_entries() -> list[DirectoryEntry]:
    entries: list[DirectoryEntry] = []
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            root = Path(f"{letter}:/")
            if root.exists():
                entries.append(DirectoryEntry(name=f"{letter}:", path=root))
    else:
        entries.append(DirectoryEntry(name="/", path=Path("/")))

    for extra in [Path.home(), Path.cwd()]:
        if extra.exists() and extra.is_dir() and all(_normalize(extra) != _normalize(entry.path) for entry in entries):
            entries.append(DirectoryEntry(name=str(extra), path=extra))
    return entries


def _parent_path(path: Path) -> Path | None:
    parent = path.parent
    return None if parent == path else parent


def _normalize(path: Path) -> str:
    return str(path.resolve(strict=False)).replace("\\", "/").rstrip("/").casefold()
