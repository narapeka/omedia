from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileDetail:
    path: Path
    exists: bool
    file_type: str
    size_bytes: int | None = None
    created_time: float | None = None
    modified_time: float | None = None
    is_symlink: bool = False
    is_reparse_point: bool = False
    safe_to_delete: bool = False
    blocked_reason: str | None = None


def inspect_path(path: Path, *, protected_root: Path | None = None) -> FileDetail:
    path = Path(path)
    if protected_root is not None and not _is_within_root(path, protected_root):
        return FileDetail(
            path=path,
            exists=path.exists(),
            file_type="outside_root",
            blocked_reason="outside_protected_root",
        )
    try:
        stat = path.lstat()
    except FileNotFoundError:
        return FileDetail(path=path, exists=False, file_type="missing")
    except OSError as exc:
        return FileDetail(path=path, exists=path.exists(), file_type="blocked", blocked_reason=type(exc).__name__)

    is_link = path.is_symlink()
    is_reparse = _is_reparse_point(stat)
    if is_link or is_reparse:
        return FileDetail(
            path=path,
            exists=True,
            file_type="link",
            size_bytes=stat.st_size,
            created_time=getattr(stat, "st_ctime", None),
            modified_time=getattr(stat, "st_mtime", None),
            is_symlink=is_link,
            is_reparse_point=is_reparse,
            blocked_reason="link_or_reparse_point",
        )
    if path.is_file():
        file_type = "file"
        safe = True
    elif path.is_dir():
        file_type = "directory"
        safe = True
    else:
        file_type = "other"
        safe = False
    return FileDetail(
        path=path,
        exists=True,
        file_type=file_type,
        size_bytes=stat.st_size if path.is_file() else None,
        created_time=getattr(stat, "st_ctime", None),
        modified_time=getattr(stat, "st_mtime", None),
        is_symlink=False,
        is_reparse_point=False,
        safe_to_delete=safe,
        blocked_reason=None if safe else "unsupported_file_type",
    )


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _is_reparse_point(stat_result) -> bool:
    attributes = getattr(stat_result, "st_file_attributes", 0)
    return bool(attributes & getattr(os.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
