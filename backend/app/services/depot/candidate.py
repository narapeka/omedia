from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.error import ConfigurationError
from app.core.path import display_sort_key, natural_sort_key
from app.domain.depot import Depot
from app.domain.media import MediaExtensionPolicy
from app.domain.depot import DepotCandidate, DepotCandidateFile, DepotCandidateKind
from app.engines.name.depot import PATH_SPLIT_UNGROUPED_ROOT_FILE, PATH_SPLIT_UNGROUPED_ROOT_FOLDER
from app.engines.scan.depot import scan_depot_candidates


@dataclass(frozen=True)
class CandidateScopeGroup:
    key: str
    organize_prefix: Path
    display_name: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "organize_prefix": self.organize_prefix.as_posix(),
            "display_name": self.display_name,
        }

    @classmethod
    def from_payload(cls, payload: object) -> "CandidateScopeGroup | None":
        if not isinstance(payload, Mapping):
            return None
        key = _optional_text(payload.get("key"))
        organize_prefix = _optional_path(payload.get("organize_prefix"))
        if key is None or organize_prefix is None:
            return None
        return cls(
            key=key,
            organize_prefix=organize_prefix,
            display_name=_optional_text(payload.get("display_name")),
        )


@dataclass(frozen=True)
class CandidateScope:
    id: str
    kind: str | None = None
    relative_path: Path | None = None
    display_name: str | None = None
    file_count: int | None = None
    size_bytes: int | None = None
    media_relative_path: Path | None = None
    path_split_confidence: str | None = None
    group: CandidateScopeGroup | None = None
    organize_prefix: Path | None = None

    @property
    def relative_path_text(self) -> str | None:
        return self.relative_path.as_posix() if self.relative_path is not None else None

    @property
    def media_relative_path_text(self) -> str | None:
        return self.media_relative_path.as_posix() if self.media_relative_path is not None else None

    @property
    def group_key(self) -> str | None:
        return self.group.key if self.group is not None else None

    @property
    def organize_prefix_text(self) -> str | None:
        if self.group is not None:
            return self.group.organize_prefix.as_posix()
        return self.organize_prefix.as_posix() if self.organize_prefix is not None else None

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "kind": self.kind,
            "relative_path": self.relative_path_text,
            "display_name": self.display_name,
            "file_count": self.file_count,
            "size_bytes": self.size_bytes,
            "media_relative_path": self.media_relative_path_text,
            "path_split_confidence": self.path_split_confidence,
        }
        if self.group is not None:
            payload["group"] = self.group.as_dict()
        if self.organize_prefix is not None:
            payload["organize_prefix"] = self.organize_prefix.as_posix()
        return payload

    @classmethod
    def from_payload(cls, payload: object) -> "CandidateScope | None":
        if isinstance(payload, CandidateScope):
            return payload
        if not isinstance(payload, Mapping):
            return None
        candidate_id = _optional_text(payload.get("id"))
        if candidate_id is None:
            return None
        return cls(
            id=candidate_id,
            kind=_optional_text(payload.get("kind")),
            relative_path=_optional_path(payload.get("relative_path")),
            display_name=_optional_text(payload.get("display_name")),
            file_count=_optional_int(payload.get("file_count")),
            size_bytes=_optional_int(payload.get("size_bytes")),
            media_relative_path=_optional_path(payload.get("media_relative_path")),
            path_split_confidence=_optional_text(payload.get("path_split_confidence")),
            group=CandidateScopeGroup.from_payload(payload.get("group")),
            organize_prefix=_optional_path(payload.get("organize_prefix")),
        )


class CandidateBook:
    def __init__(self, depot: Depot, extensions: MediaExtensionPolicy) -> None:
        self.depot = depot
        self.extensions = extensions

    def all(self) -> list[DepotCandidate]:
        return scan_depot_candidates(self.depot, self.extensions)

    def require(self, candidate_id: str) -> DepotCandidate:
        candidate = next((item for item in self.all() if item.id == candidate_id), None)
        if candidate is None:
            raise ConfigurationError(
                f"Unknown Depot candidate: {candidate_id}",
                code="depot_candidate.unknown",
                details={"depot_id": self.depot.id, "candidate_id": candidate_id},
            )
        return candidate

    def file(self, candidate_id: str, file_id: str) -> tuple[DepotCandidate, DepotCandidateFile]:
        candidate = self.require(candidate_id)
        if candidate.kind != DepotCandidateKind.FOLDER:
            raise ConfigurationError(
                "Depot candidate child file operations require a folder-backed candidate",
                code="depot_candidate.child_requires_folder",
                details={"depot_id": self.depot.id, "candidate_id": candidate_id},
            )
        file = next((item for item in candidate.files if item.id == file_id), None)
        if file is None:
            raise ConfigurationError(
                f"Unknown Depot candidate file: {file_id}",
                code="depot_candidate_file.unknown",
                details={"depot_id": self.depot.id, "candidate_id": candidate_id, "file_id": file_id},
            )
        return candidate, file

    def many(self, candidate_ids: list[str]) -> list[DepotCandidate]:
        candidates = self.all()
        by_id = {candidate.id: candidate for candidate in candidates}
        missing = [candidate_id for candidate_id in candidate_ids if candidate_id not in by_id]
        if missing:
            raise ConfigurationError(
                f"Unknown Depot candidate(s): {', '.join(missing)}",
                code="depot_candidate.unknown",
                details={"depot_id": self.depot.id, "candidate_ids": missing},
            )
        return [by_id[candidate_id] for candidate_id in candidate_ids]

    def scope(self, candidate: DepotCandidate) -> CandidateScope:
        group = None
        if candidate.group is not None:
            group = CandidateScopeGroup(
                key=candidate.group.key,
                organize_prefix=candidate.group.organize_prefix,
                display_name=candidate.group.display_name,
            )
        return CandidateScope(
            id=candidate.id,
            kind=candidate.kind.value,
            relative_path=candidate.relative_path,
            display_name=candidate.display_name,
            file_count=candidate.file_count,
            size_bytes=candidate.size_bytes,
            media_relative_path=candidate.media_relative_path,
            path_split_confidence=candidate.path_split_confidence,
            group=group,
        )

    def from_scope(self, scope: CandidateScope | Mapping[str, Any]) -> DepotCandidate | None:
        candidate_scope = CandidateScope.from_payload(scope)
        if candidate_scope is None:
            return None
        return next((candidate for candidate in self.all() if candidate.id == candidate_scope.id), None)


def sort_depot_candidates_for_read(candidates: list[DepotCandidate]) -> list[DepotCandidate]:
    return sorted(candidates, key=_depot_candidate_read_sort_key)


def _depot_candidate_read_sort_key(candidate: DepotCandidate):
    path_key = natural_sort_key(candidate.relative_path.as_posix())
    if candidate.group is None and not _is_empty_root_folder_for_read(candidate):
        return (
            0,
            display_sort_key(candidate.display_name),
            path_key,
            candidate.id,
        )
    if candidate.group is None:
        return (
            1,
            display_sort_key(candidate.display_name),
            path_key,
            display_sort_key(candidate.display_name),
            path_key,
            path_key,
            candidate.id,
        )
    return (
        1,
        display_sort_key(candidate.group.display_name),
        natural_sort_key(candidate.group.organize_prefix.as_posix()),
        display_sort_key(candidate.display_name),
        natural_sort_key((candidate.media_relative_path or candidate.relative_path).as_posix()),
        path_key,
        candidate.id,
    )


def _is_empty_root_folder_for_read(candidate: DepotCandidate) -> bool:
    return (
        candidate.group is None
        and candidate.kind == DepotCandidateKind.FOLDER
        and len(candidate.relative_path.parts) == 1
        and candidate.file_count == 0
        and candidate.blocked_reason is None
        and candidate.path_split_confidence in {PATH_SPLIT_UNGROUPED_ROOT_FILE, PATH_SPLIT_UNGROUPED_ROOT_FOLDER}
    )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_path(value: object) -> Path | None:
    text = _optional_text(value)
    return Path(text) if text else None


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None

