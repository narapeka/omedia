from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MovieTagSuffix:
    raw_tag: str
    rendered_suffix: str


@dataclass
class MovieFileSet:
    primary_file: Path
    subtitle_files: list[Path] = field(default_factory=list)
    sidecar_files: list[Path] = field(default_factory=list)


@dataclass
class MovieIdentity:
    source_name: str
    title: str | None = None
    original_title: str | None = None
    year: int | None = None
    tmdb_id: int | None = None
    tag: MovieTagSuffix | None = None
    file_set: MovieFileSet | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
