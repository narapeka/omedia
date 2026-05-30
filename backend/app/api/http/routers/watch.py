from __future__ import annotations

from fastapi import APIRouter

from app.api.http.deps import Watch
from app.api.http.present.watch import present_watch_settings, present_watch_settings_child, present_watch_status
from app.api.http.schemas.common import DEFAULT_API_RESPONSES
from app.api.http.schemas.watch import WatchSettings as WatchSettingsModel
from app.api.http.schemas.watch import WatchSettingsChild, WatchStatus
from app.domain.watch import WatchSettings as DomainWatchSettings

router = APIRouter(prefix="/watch", tags=["watch"], responses=DEFAULT_API_RESPONSES)


@router.get("/settings", response_model=WatchSettingsModel | None)
def watch_settings(watch: Watch) -> WatchSettingsModel | None:
    return present_watch_settings(watch.settings())


@router.put("/settings", response_model=WatchSettingsModel)
def save_watch_settings(payload: WatchSettingsModel, watch: Watch) -> WatchSettingsModel:
    config = watch.save_settings(DomainWatchSettings(path=payload.path, enabled=payload.enabled, id=payload.id))
    return present_watch_settings(config)


@router.get("/status", response_model=WatchStatus)
def watch_runtime_status(watch: Watch) -> WatchStatus:
    return present_watch_status(watch.status())


@router.post("/start", response_model=WatchStatus)
def start_watch_runtime(watch: Watch) -> WatchStatus:
    return present_watch_status(watch.start_watch())


@router.post("/stop", response_model=WatchStatus)
def stop_watch_runtime(watch: Watch) -> WatchStatus:
    return present_watch_status(watch.stop_watch())


@router.post("/restart", response_model=WatchStatus)
def restart_watch_runtime(watch: Watch) -> WatchStatus:
    return present_watch_status(watch.restart_watch())


@router.get("/children", response_model=list[WatchSettingsChild])
def list_watch_settings_children(watch: Watch) -> list[WatchSettingsChild]:
    return [present_watch_settings_child(child) for child in watch.children()]
