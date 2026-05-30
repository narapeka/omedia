from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.domain.media import MediaType
from app.domain.depot import DepotCandidate
from app.domain.media import MediaCandidate

@dataclass(frozen=True)
class OriginSummaryScan:
    origin_id: str
    path: Path
    media_type: MediaType
    candidate_count: int
    file_count: int
    unknown_count: int

@dataclass(frozen=True)
class DepotSummaryScan:
    depot_id: str
    path: Path
    media_type: MediaType
    pending_count: int

@dataclass(frozen=True)
class DepotDetailScan:
    depot_id: str
    path: Path
    media_type: MediaType
    candidates: list[DepotCandidate] = field(default_factory=list)

@dataclass(frozen=True)
class AdHocSourceScan:
    path: Path
    media_type: MediaType
    candidate_count: int
    file_count: int
    candidates: list[MediaCandidate] = field(default_factory=list)

@dataclass(frozen=True)
class WatchSourcePackage:
    path: Path
    rejected_reason: str | None = None
