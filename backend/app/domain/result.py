from __future__ import annotations

from enum import Enum


class ResultStatus(str, Enum):
    PENDING = "pending"
    DRY_RUN = "dry_run"
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    CONFLICT = "conflict"
    TIMEOUT = "timeout"
    FAILED = "failed"
