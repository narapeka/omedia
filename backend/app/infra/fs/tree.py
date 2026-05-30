from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TreeFootprint:
    file_count: int
    total_size: int


def footprint(root: Path) -> TreeFootprint:
    file_count = 0
    total_size = 0
    for current, _dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in files:
            path = current_path / name
            try:
                stat = path.lstat()
            except OSError:
                continue
            file_count += 1
            total_size += stat.st_size
    return TreeFootprint(file_count=file_count, total_size=total_size)


def first_link(root: Path) -> Path | None:
    if is_link(root):
        return root
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in [*dirs, *files]:
            path = current_path / name
            if is_link(path):
                return path
    return None


def is_link(path: Path) -> bool:
    try:
        stat = path.lstat()
    except OSError:
        return True
    attributes = getattr(stat, "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & getattr(os.stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
