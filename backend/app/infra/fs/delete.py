from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.infra.fs.inspect import inspect_path
from app.infra.fs.tree import first_link, footprint


class StorageDeleteStatus(str, Enum):
    SUCCEEDED = "succeeded"
    MISSING = "missing"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True)
class DeleteResult:
    status: StorageDeleteStatus
    source_path: Path
    scope: str
    message: str
    file_count: int = 0
    total_size: int = 0
    exists_after: bool = False
    blocked_reason: str | None = None
    error_type: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == StorageDeleteStatus.SUCCEEDED

    def context(self) -> dict[str, object]:
        return {
            "delete_status": self.status.value,
            "delete_scope": self.scope,
            "delete_file_count": self.file_count,
            "delete_total_size": self.total_size,
            "delete_exists_after": self.exists_after,
            "delete_blocked_reason": self.blocked_reason,
            "delete_error_type": self.error_type,
        }


def delete_verified_file(path: Path, *, protected_root: Path) -> DeleteResult:
    detail = inspect_path(path, protected_root=protected_root)
    if not detail.exists:
        return DeleteResult(StorageDeleteStatus.MISSING, path, "file", "Source file is missing", exists_after=False)
    if detail.blocked_reason:
        return DeleteResult(
            StorageDeleteStatus.BLOCKED,
            path,
            "file",
            "Source file delete is blocked",
            exists_after=path.exists(),
            blocked_reason=detail.blocked_reason,
        )
    if detail.file_type != "file":
        return DeleteResult(
            StorageDeleteStatus.BLOCKED,
            path,
            "file",
            "Source file delete requires a regular file",
            exists_after=path.exists(),
            blocked_reason="not_regular_file",
        )
    try:
        size = detail.size_bytes or 0
        path.unlink()
        return DeleteResult(
            StorageDeleteStatus.SUCCEEDED,
            path,
            "file",
            "Deleted source file",
            file_count=1,
            total_size=size,
            exists_after=path.exists(),
        )
    except Exception as exc:
        return DeleteResult(
            StorageDeleteStatus.FAILED,
            path,
            "file",
            str(exc),
            exists_after=path.exists(),
            error_type=type(exc).__name__,
        )


def delete_verified_tree(path: Path, *, protected_root: Path) -> DeleteResult:
    detail = inspect_path(path, protected_root=protected_root)
    if not detail.exists:
        return DeleteResult(StorageDeleteStatus.MISSING, path, "tree", "Source candidate is missing", exists_after=False)
    if detail.blocked_reason:
        return DeleteResult(
            StorageDeleteStatus.BLOCKED,
            path,
            "tree",
            "Source candidate delete is blocked",
            exists_after=path.exists(),
            blocked_reason=detail.blocked_reason,
        )
    if detail.file_type == "file":
        return delete_verified_file(path, protected_root=protected_root)
    if detail.file_type != "directory":
        return DeleteResult(
            StorageDeleteStatus.BLOCKED,
            path,
            "tree",
            "Source candidate delete requires a directory tree or file",
            exists_after=path.exists(),
            blocked_reason="unsupported_file_type",
        )
    blocked = first_link(path)
    if blocked is not None:
        return DeleteResult(
            StorageDeleteStatus.BLOCKED,
            path,
            "tree",
            "Source candidate tree contains a link or reparse point",
            exists_after=path.exists(),
            blocked_reason="contains_link_or_reparse_point",
        )
    try:
        tree = footprint(path)
        shutil.rmtree(path)
        return DeleteResult(
            StorageDeleteStatus.SUCCEEDED,
            path,
            "tree",
            "Deleted source candidate tree",
            file_count=tree.file_count,
            total_size=tree.total_size,
            exists_after=path.exists(),
        )
    except Exception as exc:
        return DeleteResult(
            StorageDeleteStatus.FAILED,
            path,
            "tree",
            str(exc),
            exists_after=path.exists(),
            error_type=type(exc).__name__,
        )
