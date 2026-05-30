from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import Field

from app.api.http.schemas.common import ApiModel
from app.domain.transfer import TransferErrorCode, TransferStatus, TransferTrigger


class TransferJob(ApiModel):
    id: str
    depot_id: str
    status: TransferStatus
    requested_by: str = "manual"
    error_code: TransferErrorCode | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TransferRequest(ApiModel):
    depot_id: str
    requested_by: str = "manual"
    candidate_ids: list[str] = Field(default_factory=list)


class TransferPolicy(ApiModel):
    target_library_path: Path
    trigger: TransferTrigger = TransferTrigger.MANUAL
    transfer_rule_id: str | None = None
    schedule: str | None = None
