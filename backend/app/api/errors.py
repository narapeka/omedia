from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.error import (
    ConfigurationError,
    MatchError,
    OmediaError,
)
from app.services.organize.session import OrganizeSessionConflict, OrganizeSessionError
from app.domain.transfer import TransferErrorCode
from app.services.transfer.worker import TransferRejected


ERROR_STATUS = {
    ConfigurationError: 400,
    OrganizeSessionConflict: 409,
    MatchError: 422,
    TransferRejected: 409,
}


FALLBACK_ERROR_CODES = {
    ConfigurationError: "configuration.invalid",
    OrganizeSessionConflict: "organize.session_conflict",
    OrganizeSessionError: "organize.session_error",
    MatchError: "match.failed",
    TransferRejected: "transfer.rejected",
    ValueError: "request.invalid",
}


def error_payload(code: str, message: str, *, details=None) -> dict:
    payload = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return payload


def install_exception_handlers(app: FastAPI, logger) -> None:
    @app.exception_handler(OmediaError)
    async def handle_omedia_error(_request: Request, exc: OmediaError):
        status_code = ERROR_STATUS.get(type(exc), 400)
        code = _error_code(exc)
        logger.warning("api.error", "Application error response", error_code=code, status_code=status_code, error_message=str(exc))
        return JSONResponse(
            status_code=status_code,
            content=error_payload(code, str(exc), details=_error_details(exc)),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, exc: RequestValidationError):
        logger.warning("api.validation", "Request validation failed", error_count=len(exc.errors()))
        return JSONResponse(
            status_code=422,
            content=error_payload("request.validation", "Request validation failed", details={"errors": exc.errors()}),
        )

    @app.exception_handler(ValueError)
    async def handle_value_error(_request: Request, exc: ValueError):
        logger.warning("api.validation", "Value error response", error_code="request.invalid", error_message=str(exc))
        return JSONResponse(
            status_code=422,
            content=error_payload("request.invalid", str(exc)),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, exc: Exception):
        logger.exception("api.unexpected", "Unhandled API exception", exc=exc)
        return JSONResponse(
            status_code=500,
            content=error_payload("internal.unexpected", str(exc)),
        )


def _error_code(exc: OmediaError) -> str:
    if isinstance(exc, TransferRejected):
        return _transfer_api_code(exc.code)
    code = getattr(exc, "code", None)
    if hasattr(code, "value"):
        code = code.value
    if code:
        return str(code)
    for error_type, fallback in FALLBACK_ERROR_CODES.items():
        if isinstance(exc, error_type):
            return fallback
    return "application.error"


def _error_details(exc: OmediaError):
    details = getattr(exc, "details", None)
    return details if details else None


def _transfer_api_code(code: TransferErrorCode) -> str:
    if code == TransferErrorCode.DEPOT_TRANSFER_BUSY:
        return "depot.active_transfer"
    if code == TransferErrorCode.TRANSFER_WORKER_BUSY:
        return "transfer.busy"
    if code == TransferErrorCode.DEPOT_LOCKED:
        return "depot.locked"
    return "transfer.failed"
