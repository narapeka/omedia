from __future__ import annotations

from app.api.http.schemas.inventory import DirectoryEntry, DirectoryListing, FileDetail


def present_directory_listing(listing) -> DirectoryListing:
    return DirectoryListing(
        path=listing.path,
        parent_path=listing.parent_path,
        entries=[
            DirectoryEntry(
                name=entry.name,
                path=entry.path,
                modified_time=entry.modified_time,
                blocked_reason=entry.blocked_reason,
            )
            for entry in listing.entries
        ],
        error=listing.error,
    )


def present_file_detail(detail) -> FileDetail:
    return FileDetail(
        entry_kind=getattr(detail, "entry_kind", "file"),
        path=detail.path,
        exists=detail.exists,
        file_type=detail.file_type,
        size_bytes=detail.size_bytes,
        created_time=detail.created_time,
        modified_time=detail.modified_time,
        is_symlink=detail.is_symlink,
        is_reparse_point=detail.is_reparse_point,
        safe_to_delete=detail.safe_to_delete,
        blocked_reason=detail.blocked_reason,
    )
