from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class MediaType(str, Enum):
    TV = "tv"
    MOVIE = "movie"


@dataclass(frozen=True)
class MediaFile:
    path: Path
    relative_path: Path
    extension: str
    size_bytes: int | None = None
    modified_time: float | None = None
    is_sidecar: bool = False


@dataclass(frozen=True)
class DiskFileEntry:
    path: Path
    relative_path: Path
    size_bytes: int | None = None
    modified_time: float | None = None


@dataclass(frozen=True)
class MediaExtensionPolicy:
    video: frozenset[str]
    subtitle: frozenset[str]
    sidecar: frozenset[str]

    @property
    def supported(self) -> frozenset[str]:
        return self.video | self.subtitle | self.sidecar

    @property
    def sidecar_like(self) -> frozenset[str]:
        return self.subtitle | self.sidecar


@dataclass
class MediaCandidate:
    id: str
    media_type: MediaType
    source_root: Path
    candidate_path: Path
    display_name: str
    files: list[MediaFile] = field(default_factory=list)
    structure: str | None = None
    fingerprint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
