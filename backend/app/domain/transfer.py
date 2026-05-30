from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TransferTrigger(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class TransferStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TransferErrorCode(str, Enum):
    TRANSFER_WORKER_BUSY = "transfer_worker_busy"
    DEPOT_TRANSFER_BUSY = "depot_transfer_busy"
    DEPOT_LOCKED = "depot_locked"
    MOVE_FAILED = "move_failed"
    INTERRUPTED = "interrupted"


@dataclass
class TransferJob:
    id: str
    depot_id: str
    status: TransferStatus = TransferStatus.QUEUED
    requested_by: str = "manual"
    error_code: TransferErrorCode | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
