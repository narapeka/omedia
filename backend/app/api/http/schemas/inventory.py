from __future__ import annotations

from pathlib import Path

from app.api.http.schemas.common import ApiModel


class DirectoryEntry(ApiModel):
    name: str
    path: Path
    modified_time: float | None = None
    blocked_reason: str | None = None


class DirectoryListing(ApiModel):
    path: Path | None
    parent_path: Path | None
    entries: list[DirectoryEntry]
    error: str | None = None


class FileDetail(ApiModel):
    entry_kind: str = "file"
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
