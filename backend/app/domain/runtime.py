from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class WorkerStatus:
    id: str
    label: str
    running: bool
    state: str
    current_item_id: str | None = None
    last_error: str | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None


class BackgroundWorker(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def status(self) -> WorkerStatus:
        ...
