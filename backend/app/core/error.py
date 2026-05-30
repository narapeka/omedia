from __future__ import annotations

from enum import Enum
from typing import Any, Mapping


class OmediaError(Exception):
    """Base error for modern organizer failures."""

    def __init__(
        self,
        message: str = "",
        *,
        code: str | Enum | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = _code_value(code) if code is not None else None
        self.details = dict(details or {})


class ConfigurationError(OmediaError):
    """Configuration is missing, invalid, or unsafe."""


class MatchError(OmediaError):
    """match failed or produced invalid evidence."""


def _code_value(code: str | Enum) -> str:
    return str(code.value if isinstance(code, Enum) else code)
