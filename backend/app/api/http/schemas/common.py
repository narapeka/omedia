from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)


class ApiErrorDetail(ApiModel):
    code: str
    message: str
    details: Any | None = None


class ApiErrorResponse(ApiModel):
    error: ApiErrorDetail


DEFAULT_API_RESPONSES = {
    400: {"model": ApiErrorResponse, "description": "Application error"},
    409: {"model": ApiErrorResponse, "description": "State conflict"},
    422: {"model": ApiErrorResponse, "description": "Validation or domain error"},
    500: {"model": ApiErrorResponse, "description": "Unexpected server error"},
}
