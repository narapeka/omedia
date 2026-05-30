from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.domain.depot import (
    DepotCandidate,
    DepotCandidateFile,
    DepotCandidateKind,
    depot_candidate_file_id,
    depot_candidate_id,
)
from app.domain.depot import Depot
from app.domain.media import DiskFileEntry, MediaExtensionPolicy
from app.engines.name.depot import group_for_organize_prefix, is_system_media_root_name, split_depot_relative_path

from app.engines.scan.types import DepotDetailScan, DepotSummaryScan

def scan_depot_summary(depot: Depot, extensions: MediaExtensionPolicy) -> DepotSummaryScan:
    candidates = scan_depot_candidates(depot, extensions)
    return DepotSummaryScan(
        depot_id=depot.id,
        path=depot.path,
        media_type=depot.media_type,
        pending_count=sum(candidate.file_count for candidate in candidates),
    )

def scan_depot_detail_tree(depot: Depot, extensions: MediaExtensionPolicy) -> DepotDetailScan:
    return DepotDetailScan(
        depot_id=depot.id,
        path=depot.path,
        media_type=depot.media_type,
        candidates=scan_depot_candidates(depot, extensions),
    )

def scan_depot_candidates(depot: Depot, extensions: MediaExtensionPolicy) -> list[DepotCandidate]:
    root = depot.path
    if not root.exists() or not root.is_dir():
        return []
    candidates: list[DepotCandidate] = []
    for child in sorted(root.iterdir(), key=lambda path: path.name.casefold()):
        if _is_link_or_reparse(child):
            kind = DepotCandidateKind.FOLDER if child.is_dir() else DepotCandidateKind.FILE
            candidates.append(_blocked_depot_candidate(depot, child, kind, "link_or_reparse_point"))
            continue
        if child.is_dir():
            media_roots = _marked_depot_media_roots(root, child)
            if media_roots:
                candidates.extend(_folder_depot_candidate(depot, media_root, extensions) for media_root in media_roots)
            else:
                candidates.append(_folder_depot_candidate(depot, child, extensions))
        elif child.is_file():
            candidates.append(_file_depot_candidate(depot, child, extensions))
    return candidates

def expand_depot_candidate_files(candidates: list[DepotCandidate]) -> list[DiskFileEntry]:
    files: list[DiskFileEntry] = []
    for candidate in candidates:
        if candidate.kind == DepotCandidateKind.FILE:
            if candidate.blocked_reason:
                continue
            files.append(
                DiskFileEntry(
                    path=candidate.path,
                    relative_path=candidate.relative_path,
                    size_bytes=candidate.size_bytes,
                    modified_time=candidate.modified_time,
                )
            )
            continue
        files.extend(
            DiskFileEntry(
                path=file.path,
                relative_path=file.relative_path,
                size_bytes=file.size_bytes,
                modified_time=file.modified_time,
            )
            for file in candidate.files
            if not file.blocked_reason
        )
    return sorted(files, key=lambda item: item.relative_path.as_posix().casefold())

def _marked_depot_media_roots(depot_root: Path, search_root: Path) -> list[Path]:
    roots: list[Path] = []
    for current_text, dirs, _filenames in os.walk(search_root, topdown=True, followlinks=False):
        current = Path(current_text)
        if _is_link_or_reparse(current):
            dirs[:] = []
            continue
        if is_system_media_root_name(current.name):
            roots.append(current)
            dirs[:] = []
            continue
        kept_dirs: list[str] = []
        for dirname in dirs:
            directory = current / dirname
            if _is_link_or_reparse(directory):
                continue
            kept_dirs.append(dirname)
        dirs[:] = kept_dirs
    return sorted(roots, key=lambda path: path.relative_to(depot_root).as_posix().casefold())

def _file_depot_candidate(depot: Depot, path: Path, extensions: MediaExtensionPolicy) -> DepotCandidate:
    try:
        stat_result = path.lstat()
    except OSError as exc:
        return _blocked_depot_candidate(depot, path, DepotCandidateKind.FILE, type(exc).__name__)
    relative_path = path.relative_to(depot.path)
    split = split_depot_relative_path(relative_path)
    size = stat_result.st_size
    return DepotCandidate(
        id=depot_candidate_id(depot.id, DepotCandidateKind.FILE, relative_path),
        kind=DepotCandidateKind.FILE,
        path=path,
        relative_path=relative_path,
        display_name=path.name,
        size_bytes=size,
        modified_time=stat_result.st_mtime,
        file_count=1,
        media_count=1 if path.suffix.lower() in (extensions.video | extensions.subtitle) else 0,
        group=group_for_organize_prefix(depot.id, split.organize_prefix),
        media_relative_path=split.media_relative_path,
        path_split_confidence=split.confidence,
    )

def _folder_depot_candidate(depot: Depot, path: Path, extensions: MediaExtensionPolicy) -> DepotCandidate:
    candidate_relative_path = path.relative_to(depot.path)
    split = split_depot_relative_path(candidate_relative_path)
    files: list[DepotCandidateFile] = []
    blocked_reason: str | None = None
    latest_mtime: float | None = None
    total_size = 0
    try:
        folder_stat = path.lstat()
        latest_mtime = folder_stat.st_mtime
    except OSError as exc:
        return _blocked_depot_candidate(depot, path, DepotCandidateKind.FOLDER, type(exc).__name__)

    for current_text, dirs, filenames in os.walk(path, topdown=True, followlinks=False):
        current = Path(current_text)
        kept_dirs: list[str] = []
        for dirname in dirs:
            directory = current / dirname
            if _is_link_or_reparse(directory):
                blocked_reason = blocked_reason or "contains_link_or_reparse_point"
                continue
            kept_dirs.append(dirname)
        dirs[:] = kept_dirs

        for filename in filenames:
            file_path = current / filename
            if _is_link_or_reparse(file_path):
                blocked_reason = blocked_reason or "contains_link_or_reparse_point"
                continue
            if not file_path.is_file():
                blocked_reason = blocked_reason or "contains_non_regular_file"
                continue
            try:
                stat_result = file_path.lstat()
            except OSError:
                blocked_reason = blocked_reason or "scan_error"
                continue
            depot_relative_path = file_path.relative_to(depot.path)
            child_relative_path = file_path.relative_to(path)
            total_size += stat_result.st_size
            latest_mtime = max(latest_mtime or stat_result.st_mtime, stat_result.st_mtime)
            files.append(
                DepotCandidateFile(
                    id=depot_candidate_file_id(depot.id, depot_relative_path),
                    path=file_path,
                    relative_path=depot_relative_path,
                    candidate_relative_path=child_relative_path,
                    display_name=file_path.name,
                    size_bytes=stat_result.st_size,
                    modified_time=stat_result.st_mtime,
                    extension=file_path.suffix.lower(),
                    is_media=file_path.suffix.lower() in (extensions.video | extensions.subtitle),
                )
            )

    files = sorted(files, key=lambda file: file.candidate_relative_path.as_posix().casefold())
    return DepotCandidate(
        id=depot_candidate_id(depot.id, DepotCandidateKind.FOLDER, candidate_relative_path),
        kind=DepotCandidateKind.FOLDER,
        path=path,
        relative_path=candidate_relative_path,
        display_name=path.name,
        size_bytes=total_size,
        modified_time=latest_mtime,
        file_count=len(files),
        media_count=sum(1 for file in files if file.is_media),
        group=group_for_organize_prefix(depot.id, split.organize_prefix),
        media_relative_path=split.media_relative_path,
        path_split_confidence=split.confidence,
        files=files,
        tree=_candidate_tree_from_files(files),
        blocked_reason=blocked_reason,
    )

def _blocked_depot_candidate(depot: Depot, path: Path, kind: DepotCandidateKind, reason: str) -> DepotCandidate:
    try:
        relative_path = path.relative_to(depot.path)
    except ValueError:
        relative_path = Path(path.name)
    try:
        stat_result = path.lstat()
        modified_time = stat_result.st_mtime
        size_bytes = stat_result.st_size if kind == DepotCandidateKind.FILE else 0
    except OSError:
        modified_time = None
        size_bytes = 0
    split = split_depot_relative_path(relative_path)
    return DepotCandidate(
        id=depot_candidate_id(depot.id, kind, relative_path),
        kind=kind,
        path=path,
        relative_path=relative_path,
        display_name=path.name,
        size_bytes=size_bytes,
        modified_time=modified_time,
        group=group_for_organize_prefix(depot.id, split.organize_prefix),
        media_relative_path=split.media_relative_path,
        path_split_confidence=split.confidence,
        blocked_reason=reason,
    )

def _candidate_tree_from_files(files: list[DepotCandidateFile]) -> dict[str, Any]:
    root: dict[str, Any] = {"name": "", "dirs": {}, "files": []}
    for file in files:
        node = root
        parts = file.candidate_relative_path.parts
        for part in parts[:-1]:
            node = node["dirs"].setdefault(part, {"name": part, "dirs": {}, "files": []})
        node["files"].append(
            {
                "id": file.id,
                "name": parts[-1] if parts else file.path.name,
                "relative_path": file.relative_path.as_posix(),
                "candidate_relative_path": file.candidate_relative_path.as_posix(),
                "size_bytes": file.size_bytes,
                "modified_time": file.modified_time,
                "is_media": file.is_media,
                "blocked_reason": file.blocked_reason,
            }
        )
    return _sort_tree(root)

def _is_link_or_reparse(path: Path) -> bool:
    try:
        stat_result = path.lstat()
    except OSError:
        return True
    attributes = getattr(stat_result, "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & getattr(os.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))

def _sort_tree(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": node["name"],
        "dirs": [_sort_tree(node["dirs"][key]) for key in sorted(node["dirs"])],
        "files": sorted(node["files"], key=lambda item: item["relative_path"].lower()),
    }

