from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import Iterable
import sys
from pathlib import Path
from typing import Literal

from app.infra.log.app import app_log
from app.api.errors import install_exception_handlers
from app.api.http.routers import api_router as http_api_router
from app.boot.manager import RuntimeManager
from app.boot.runtime import (
    RuntimeContext,
    RuntimeSettings,
    create_runtime_context_from_settings,
    resolve_runtime_settings,
)


def create_runtime() -> RuntimeContext:
    return create_runtime_context_from_settings(resolve_runtime_settings(cwd=_workspace_root()))


def create_app(
    *,
    runtime: RuntimeContext | None = None,
    settings: RuntimeSettings | None = None,
    cors_origins: Iterable[str] | None = None,
    openapi_surface: Literal["target"] = "target",
    static_dir: str | Path | None = None,
):
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    runtime_settings = settings or _settings_from_runtime(runtime) or resolve_runtime_settings(cwd=_workspace_root())
    runtime_manager = RuntimeManager(runtime_settings, runtime)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime_manager.start()
        try:
            yield
        finally:
            app.state.runtime_manager.stop()

    app = FastAPI(
        title="OMEDIA",
        version="0.1.0",
        description="Disk-first media organization API.",
        generate_unique_id_function=_stable_operation_id,
        separate_input_output_schemas=False,
        lifespan=lifespan,
    )
    app.state.runtime_settings = runtime_settings
    app.state.runtime_manager = runtime_manager

    origins = list(cors_origins or _default_cors_origins())
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if openapi_surface != "target":
        raise ValueError("Only the clean target API surface is available after contract cleanup")
    app.include_router(http_api_router, prefix="/api", include_in_schema=True)
    install_exception_handlers(app, app_log)
    _install_static_frontend(app, static_dir)

    return app


def _stable_operation_id(route) -> str:
    """Keep OpenAPI operation IDs readable for generated frontend imports."""
    try:
        from fastapi.routing import APIRoute
    except ImportError:
        return getattr(route, "name", None) or "operation"
    if isinstance(route, APIRoute):
        return route.name
    return getattr(route, "name", None) or "operation"


def reload_runtime(app) -> RuntimeContext:
    return app.state.runtime_manager.reload()


def _default_cors_origins() -> tuple[str, ...]:
    return (
        "http://localhost:7108",
        "http://127.0.0.1:7108",
        "http://localhost:7109",
        "http://127.0.0.1:7109",
    )


def _install_static_frontend(app, static_dir: str | Path | None) -> None:
    root = Path(static_dir) if static_dir is not None else _default_static_dir()
    if root is None:
        return
    index_path = root / "index.html"
    if not index_path.is_file():
        return

    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    @app.get("/", include_in_schema=False)
    def frontend_index():
        return FileResponse(index_path)

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend_asset_or_index(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = _safe_static_file(root, full_path)
        if candidate is not None:
            return FileResponse(candidate)
        return FileResponse(index_path)


def _safe_static_file(root: Path, full_path: str) -> Path | None:
    if not full_path or "\x00" in full_path:
        return None
    try:
        candidate = (root / full_path).resolve(strict=False)
        candidate.relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return None
    if candidate.is_file():
        return candidate
    return None


def _default_static_dir() -> Path | None:
    for candidate in _static_dir_candidates():
        if (candidate / "index.html").is_file():
            return candidate
    return None


def _static_dir_candidates() -> tuple[Path, ...]:
    bundle_root = Path(getattr(sys, "_MEIPASS", ""))
    return (
        bundle_root / "frontend" / "dist",
        Path.cwd() / "frontend" / "dist",
        _workspace_root() / "frontend" / "dist",
    )


def _settings_from_runtime(runtime: RuntimeContext | None) -> RuntimeSettings | None:
    if runtime is None:
        return None
    return RuntimeSettings(common_path=runtime.common_path, db_path=runtime.db_path)


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


app = create_app()
