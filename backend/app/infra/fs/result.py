from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from app.infra.fs.constants import MOVE_TIMEOUT_SECONDS


class StorageMoveStatus(str, Enum):
    SUCCEEDED = "succeeded"
    TIMEOUT = "timeout"
    FAILED = "failed"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class CleanupResult:
    attempted: bool = False
    removed_dirs: list[str] = field(default_factory=list)
    removed_files: list[str] = field(default_factory=list)
    stopped_at: str | None = None
    stop_reason: str | None = None
    error_type: str | None = None
    message: str | None = None

    def context(self) -> dict[str, Any]:
        return {
            "cleanup_attempted": self.attempted,
            "cleanup_removed_dirs": self.removed_dirs,
            "cleanup_removed_files": self.removed_files,
            "cleanup_stopped_at": self.stopped_at,
            "cleanup_stop_reason": self.stop_reason,
            "cleanup_error_type": self.error_type,
            "cleanup_message": self.message,
        }


@dataclass(frozen=True)
class MoveResult:
    status: StorageMoveStatus
    source_path: Path
    destination_path: Path
    message: str
    error_type: str | None = None
    timed_out: bool = False
    source_exists_after: bool | None = None
    destination_exists_after: bool | None = None
    cleanup: CleanupResult | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == StorageMoveStatus.SUCCEEDED

    @property
    def retryable_timeout(self) -> bool:
        return self.status == StorageMoveStatus.TIMEOUT and self.source_exists_after is True

    def context(self) -> dict[str, Any]:
        context: dict[str, Any] = {
            "move_timed_out": self.timed_out,
            "move_timeout_seconds": MOVE_TIMEOUT_SECONDS,
            "move_status": self.status.value,
            "move_source_exists_after": self.source_exists_after,
            "move_destination_exists_after": self.destination_exists_after,
            "move_error_type": self.error_type,
        }
        if self.cleanup is not None:
            context.update(self.cleanup.context())
        return {key: value for key, value in context.items() if value is not None}
