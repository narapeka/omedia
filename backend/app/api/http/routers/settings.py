from __future__ import annotations

from fastapi import APIRouter

from app.api.http.deps import Config
from app.api.http.present.config import present_settings_health
from app.api.http.present.settings import present_organize_settings, present_provider_status, present_watch_runtime_settings
from app.api.http.schemas.common import DEFAULT_API_RESPONSES
from app.api.http.schemas.config import (
    OrganizeSettings,
    ProviderSettingsUpdate,
    ProviderStatus,
    SettingsHealth,
    WatchRuntimeSettings,
)

router = APIRouter(prefix="/settings", tags=["settings"], responses=DEFAULT_API_RESPONSES)


@router.get("/health", response_model=SettingsHealth)
def settings_health(config: Config) -> SettingsHealth:
    return present_settings_health(config.health())


@router.get("/providers", response_model=ProviderStatus)
def provider_settings(config: Config) -> ProviderStatus:
    return present_provider_status(config.providers())


@router.put("/providers", response_model=ProviderStatus)
def save_provider_settings(
    payload: ProviderSettingsUpdate,
    config: Config,
) -> ProviderStatus:
    providers = config.save_provider_settings(payload.model_dump(exclude_unset=True))
    return present_provider_status(providers)


@router.get("/organize", response_model=OrganizeSettings)
def organize_settings(config: Config) -> OrganizeSettings:
    return present_organize_settings(config.organize_settings())


@router.put("/organize", response_model=OrganizeSettings)
def save_organize_settings(
    payload: OrganizeSettings,
    config: Config,
) -> OrganizeSettings:
    settings = config.save_organize_settings(payload.model_dump())
    return present_organize_settings(settings)


@router.get("/watch-runtime", response_model=WatchRuntimeSettings)
def watch_runtime_settings(config: Config) -> WatchRuntimeSettings:
    return present_watch_runtime_settings(config.watch_runtime_settings())


@router.put("/watch-runtime", response_model=WatchRuntimeSettings)
def save_watch_runtime_settings(
    payload: WatchRuntimeSettings,
    config: Config,
) -> WatchRuntimeSettings:
    settings = config.save_watch_runtime_settings(payload.model_dump())
    return present_watch_runtime_settings(settings)
