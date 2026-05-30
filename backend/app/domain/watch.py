from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WatchSettings:
    path: Path
    enabled: bool = True
    id: str = "main"
    metadata: dict[str, Any] = field(default_factory=dict)
