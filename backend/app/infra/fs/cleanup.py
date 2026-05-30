from __future__ import annotations

import shutil
import stat
from collections.abc import Collection
from pathlib import Path

from app.infra.fs.constants import JUNK_NAMES
from app.infra.fs.result import CleanupResult


def cleanup_source_parents(
    start_parent: Path,
    protected_root: Path,
    sidecar_extensions: Collection[str],
    stop_root: Path | None = None,
    subtitle_extensions: Collection[str] | None = None,
    min_non_subtitle_file_size_bytes: int | None = None,
) -> CleanupResult:
    root = protected_root.expanduser().resolve(strict=False)
    stop = (stop_root or protected_root).expanduser().resolve(strict=False)
    current = start_parent.expanduser().resolve(strict=False)
    extensions = _normalized_extensions(sidecar_extensions)
    subtitles = _normalized_extensions(subtitle_extensions or ())
    removed_dirs: list[str] = []
    removed_files: list[str] = []
    try:
        current.relative_to(root)
    except ValueError:
        return CleanupResult(
            attempted=False,
            stopped_at=_path_text(current),
            stop_reason="outside_protected_root",
        )

    try:
        stop.relative_to(root)
    except ValueError:
        return CleanupResult(
            attempted=False,
            stopped_at=_path_text(stop),
            stop_reason="stop_outside_protected_root",
        )
    try:
        current.relative_to(stop)
    except ValueError:
        return CleanupResult(
            attempted=False,
            stopped_at=_path_text(current),
            stop_reason="outside_stop_root",
        )

    while current != stop:
        if not current.exists():
            removed_dirs.append(_relative_path_text(current, root))
            current = current.parent
            continue
        if not current.is_dir() or _is_reparse_or_symlink(current):
            return CleanupResult(
                attempted=True,
                removed_dirs=removed_dirs,
                removed_files=removed_files,
                stopped_at=_relative_path_text(current, root),
                stop_reason="not_prunable",
            )
        try:
            current.rmdir()
            removed_dirs.append(_relative_path_text(current, root))
            current = current.parent
            continue
        except OSError:
            pass

        prunable = _prunable_tree(
            current,
            root,
            extensions,
            subtitle_extensions=subtitles,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
        )
        if not prunable.prunable:
            return CleanupResult(
                attempted=True,
                removed_dirs=removed_dirs,
                removed_files=removed_files,
                stopped_at=_relative_path_text(current, root),
                stop_reason=prunable.reason,
            )
        try:
            shutil.rmtree(current)
            removed_dirs.append(_relative_path_text(current, root))
            removed_files.extend(prunable.files)
            current = current.parent
        except Exception as exc:
            return CleanupResult(
                attempted=True,
                removed_dirs=removed_dirs,
                removed_files=removed_files,
                stopped_at=_relative_path_text(current, root),
                stop_reason="cleanup_error",
                error_type=type(exc).__name__,
                message=str(exc),
            )

    return CleanupResult(
        attempted=True,
        removed_dirs=removed_dirs,
        removed_files=removed_files,
        stopped_at=_relative_path_text(stop, root),
        stop_reason="stop_root" if stop != root else "protected_root",
    )


class _PrunableTree:
    def __init__(self, *, prunable: bool, reason: str, files: list[str] | None = None):
        self.prunable = prunable
        self.reason = reason
        self.files = files or []


def _prunable_tree(
    path: Path,
    root: Path,
    sidecar_extensions: frozenset[str],
    *,
    subtitle_extensions: frozenset[str],
    min_non_subtitle_file_size_bytes: int | None,
) -> _PrunableTree:
    files: list[str] = []
    has_file = False
    try:
        for child in path.rglob("*"):
            if _is_reparse_or_symlink(child):
                return _PrunableTree(prunable=False, reason="contains_link_or_reparse_point")
            if child.is_dir():
                continue
            if not child.is_file():
                return _PrunableTree(prunable=False, reason="contains_non_file_entry")
            has_file = True
            if not _is_prunable_file(
                child,
                sidecar_extensions=sidecar_extensions,
                subtitle_extensions=subtitle_extensions,
                min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
            ):
                return _PrunableTree(prunable=False, reason="contains_non_sidecar")
            files.append(_relative_path_text(child, root))
    except OSError as exc:
        return _PrunableTree(prunable=False, reason=f"scan_error:{type(exc).__name__}")
    if not has_file:
        return _PrunableTree(prunable=True, reason="empty_tree", files=files)
    return _PrunableTree(prunable=True, reason="sidecar_only", files=files)


def _is_prunable_file(
    path: Path,
    *,
    sidecar_extensions: frozenset[str],
    subtitle_extensions: frozenset[str],
    min_non_subtitle_file_size_bytes: int | None,
) -> bool:
    if path.name in JUNK_NAMES:
        return True
    extension = path.suffix.lower()
    if extension in sidecar_extensions:
        return True
    if not min_non_subtitle_file_size_bytes or extension in subtitle_extensions:
        return False
    try:
        return path.stat().st_size < min_non_subtitle_file_size_bytes
    except OSError:
        return False


def _is_reparse_or_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attrs = path.lstat().st_file_attributes
    except AttributeError:
        return False
    except OSError:
        return True
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _normalized_extensions(sidecar_extensions: Collection[str]) -> frozenset[str]:
    normalized = []
    for extension in sidecar_extensions:
        text = str(extension).strip().lower()
        if not text:
            continue
        normalized.append(text if text.startswith(".") else f".{text}")
    return frozenset(normalized)


def _relative_path_text(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix() or "."
    except ValueError:
        return _path_text(path)


def _path_text(path: Path) -> str:
    return path.as_posix()
