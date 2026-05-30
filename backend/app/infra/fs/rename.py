from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.infra.fs.inspect import inspect_path
from app.infra.fs.tree import first_link, footprint


class StorageRenameStatus(str, Enum):
    SUCCEEDED = "succeeded"
    MISSING = "missing"
    CONFLICT = "conflict"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class RenameResult:
    status: StorageRenameStatus
    old_path: Path
    new_path: Path
    scope: str
    message: str
    file_count: int = 0
    total_size: int = 0
    exists_after_old: bool = False
    exists_after_new: bool = False
    blocked_reason: str | None = None
    error_type: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == StorageRenameStatus.SUCCEEDED

    def context(self) -> dict[str, object]:
        return {
            "rename_status": self.status.value,
            "rename_scope": self.scope,
            "rename_old_path": str(self.old_path),
            "rename_new_path": str(self.new_path),
            "rename_file_count": self.file_count,
            "rename_total_size": self.total_size,
            "rename_exists_after_old": self.exists_after_old,
            "rename_exists_after_new": self.exists_after_new,
            "rename_blocked_reason": self.blocked_reason,
            "rename_error_type": self.error_type,
        }


def rename_verified_file(path: Path, new_name: str, *, protected_root: Path) -> RenameResult:
    name, target, name_error = _rename_target(path, new_name)
    if name_error is not None:
        return _blocked(path, target, "file", "Source file rename is blocked", name_error)

    detail = inspect_path(path, protected_root=protected_root)
    if not detail.exists:
        return RenameResult(StorageRenameStatus.MISSING, path, target, "file", "Source file is missing", exists_after_old=False)
    if detail.blocked_reason:
        return _blocked(path, target, "file", "Source file rename is blocked", detail.blocked_reason)
    if detail.file_type != "file":
        return _blocked(path, target, "file", "Source file rename requires a regular file", "not_regular_file")

    target_error = _target_error(target, protected_root=protected_root)
    if target_error is not None:
        status = StorageRenameStatus.CONFLICT if target_error == "target_exists" else StorageRenameStatus.BLOCKED
        return RenameResult(
            status,
            path,
            target,
            "file",
            "Source file rename target is not available",
            file_count=1,
            total_size=detail.size_bytes or 0,
            exists_after_old=path.exists(),
            exists_after_new=target.exists(),
            blocked_reason=target_error,
        )

    try:
        size = detail.size_bytes or 0
        path.rename(target)
        return RenameResult(
            StorageRenameStatus.SUCCEEDED,
            path,
            target,
            "file",
            f"Renamed source file to {name}",
            file_count=1,
            total_size=size,
            exists_after_old=path.exists(),
            exists_after_new=target.exists(),
        )
    except Exception as exc:
        return RenameResult(
            StorageRenameStatus.FAILED,
            path,
            target,
            "file",
            str(exc),
            file_count=1,
            total_size=detail.size_bytes or 0,
            exists_after_old=path.exists(),
            exists_after_new=target.exists(),
            error_type=type(exc).__name__,
        )


def rename_verified_tree(path: Path, new_name: str, *, protected_root: Path) -> RenameResult:
    name, target, name_error = _rename_target(path, new_name)
    if name_error is not None:
        return _blocked(path, target, "tree", "Source candidate rename is blocked", name_error)

    detail = inspect_path(path, protected_root=protected_root)
    if not detail.exists:
        return RenameResult(StorageRenameStatus.MISSING, path, target, "tree", "Source candidate is missing", exists_after_old=False)
    if detail.blocked_reason:
        return _blocked(path, target, "tree", "Source candidate rename is blocked", detail.blocked_reason)
    if detail.file_type != "directory":
        return _blocked(path, target, "tree", "Source candidate rename requires a directory tree", "not_directory")
    if first_link(path) is not None:
        return _blocked(
            path,
            target,
            "tree",
            "Source candidate tree contains a link or reparse point",
            "contains_link_or_reparse_point",
        )

    target_error = _target_error(target, protected_root=protected_root)
    if target_error is not None:
        status = StorageRenameStatus.CONFLICT if target_error == "target_exists" else StorageRenameStatus.BLOCKED
        tree = footprint(path)
        return RenameResult(
            status,
            path,
            target,
            "tree",
            "Source candidate rename target is not available",
            file_count=tree.file_count,
            total_size=tree.total_size,
            exists_after_old=path.exists(),
            exists_after_new=target.exists(),
            blocked_reason=target_error,
        )

    try:
        tree = footprint(path)
        path.rename(target)
        return RenameResult(
            StorageRenameStatus.SUCCEEDED,
            path,
            target,
            "tree",
            f"Renamed source candidate to {name}",
            file_count=tree.file_count,
            total_size=tree.total_size,
            exists_after_old=path.exists(),
            exists_after_new=target.exists(),
        )
    except Exception as exc:
        return RenameResult(
            StorageRenameStatus.FAILED,
            path,
            target,
            "tree",
            str(exc),
            exists_after_old=path.exists(),
            exists_after_new=target.exists(),
            error_type=type(exc).__name__,
        )


def _rename_target(path: Path, new_name: str) -> tuple[str, Path, str | None]:
    name = str(new_name).strip()
    if not name:
        return name, path.parent, "empty_name"
    if name in {".", ".."}:
        return name, path.parent / name, "relative_name"
    if any(separator and separator in name for separator in ("/", "\\", os.sep, os.altsep)):
        return name, path.parent / name, "path_separator"
    target = path.with_name(name)
    return name, target, None


def _target_error(target: Path, *, protected_root: Path) -> str | None:
    if not _is_within_root(target, protected_root):
        return "outside_protected_root"
    if target.exists():
        return "target_exists"
    return None


def _blocked(path: Path, target: Path, scope: str, message: str, reason: str) -> RenameResult:
    return RenameResult(
        StorageRenameStatus.BLOCKED,
        path,
        target,
        scope,
        message,
        exists_after_old=path.exists(),
        exists_after_new=target.exists(),
        blocked_reason=reason,
    )


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False
