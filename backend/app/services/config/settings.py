from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

import yaml

from app.core.error import ConfigurationError
from app.infra.log.app import app_log
from app.services.config.values import (
    OrganizeSettings,
    ProviderSettings,
    StartupSettings,
    WatchRuntimeSettings,
    parse_organize_settings,
    parse_provider_settings,
    parse_watch_settings,
)


class SettingsRuntimeEffects(Protocol):
    def providers_changed(self, settings: ProviderSettings) -> None:
        ...

    def organize_changed(self, settings: OrganizeSettings) -> None:
        ...

    def watch_changed(self, settings: WatchRuntimeSettings) -> None:
        ...

    def configuration_restored(self) -> None:
        ...


class SettingsFile:
    def __init__(self, common_path: Path, startup_settings: StartupSettings) -> None:
        self.common_path = Path(common_path)
        self.startup_settings = startup_settings

    @property
    def providers(self) -> ProviderSettings:
        return self.startup_settings.providers

    @property
    def organize(self) -> OrganizeSettings:
        return self.startup_settings.organize

    @property
    def watch(self) -> WatchRuntimeSettings:
        return self.startup_settings.watch

    def save_provider_settings(self, payload: dict[str, Any]) -> ProviderSettings:
        provider_data = _provider_data_from_update(self.startup_settings.providers, payload)
        providers = parse_provider_settings(provider_data)
        self.write_providers(providers)
        app_log.info("settings.providers", "Provider settings saved", tmdb_base_url=providers.tmdb_base_url, llm_base_url=providers.llm_base_url)
        return providers

    def save_organize_settings(self, payload: dict[str, Any]) -> OrganizeSettings:
        settings = self.write_organize(payload)
        app_log.info(
            "settings.organize",
            "Organize settings saved",
            video_count=len(settings.extensions.video),
            subtitle_count=len(settings.extensions.subtitle),
            sidecar_count=len(settings.extensions.sidecar),
            min_non_subtitle_file_size_mb=settings.min_non_subtitle_file_size_mb,
        )
        return settings

    def save_watch_runtime_settings(self, payload: dict[str, Any]) -> WatchRuntimeSettings:
        settings = self.write_watch(payload)
        app_log.info("settings.watch", "Watch runtime settings saved", poll_interval_seconds=settings.poll_interval_seconds, debounce_seconds=settings.stability_debounce_seconds)
        return settings

    def write_organize(self, settings: Mapping[str, Any]) -> OrganizeSettings:
        organize = parse_organize_settings({"organize": dict(settings)})
        data = read_common(self.common_path)
        data["organize"] = organize_settings_data(organize)
        write_common(self.common_path, data)
        self.startup_settings.organize = organize
        return organize

    def write_providers(self, settings: ProviderSettings) -> ProviderSettings:
        settings.require_identify()
        data = read_common(self.common_path)
        provider_data = provider_common_data(settings)
        data["tmdb"] = compact(provider_data["tmdb"])
        data["llm"] = compact(provider_data["llm"])
        write_common(self.common_path, data)
        self.startup_settings.providers = settings
        return settings

    def write_watch(self, settings: Mapping[str, Any]) -> WatchRuntimeSettings:
        watch = parse_watch_settings({"watch": dict(settings)})
        data = read_common(self.common_path)
        data["watch"] = watch_runtime_data(watch)
        write_common(self.common_path, data)
        self.startup_settings.watch = watch
        return watch


def organize_settings_data(settings) -> dict[str, Any]:
    return {
        "extensions": {
            "video": sorted(settings.extensions.video),
            "subtitle": sorted(settings.extensions.subtitle),
            "sidecar": sorted(settings.extensions.sidecar),
        },
        "min_non_subtitle_file_size_mb": settings.min_non_subtitle_file_size_mb or 0,
    }


def watch_runtime_data(settings) -> dict[str, Any]:
    return {
        "poll_interval_seconds": settings.poll_interval_seconds,
        "stability_debounce_seconds": settings.stability_debounce_seconds,
    }


def provider_common_data(settings: ProviderSettings) -> dict[str, dict[str, Any]]:
    return {
        "tmdb": {
            "api_key": settings.tmdb_api_key,
            "base_url": settings.tmdb_base_url,
            "rate_limit": settings.tmdb_rate_limit,
            "proxy": settings.tmdb_proxy,
        },
        "llm": {
            "api_key": settings.llm_api_key,
            "base_url": settings.llm_base_url,
            "model": settings.llm_model,
            "batch_size": settings.llm_batch_size,
            "rate_limit": settings.llm_rate_limit,
            "proxy": settings.llm_proxy,
        },
    }


def read_common(path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def write_common(path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def compact(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value not in (None, "")}


def _provider_data_from_update(current: ProviderSettings, payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "tmdb": {
            "api_key": _next_secret(current.tmdb_api_key, payload, "tmdb_api_key", "TMDB"),
            "base_url": payload.get("tmdb_base_url"),
            "rate_limit": payload.get("tmdb_rate_limit"),
            "proxy": payload.get("tmdb_proxy"),
        },
        "llm": {
            "api_key": _next_secret(current.llm_api_key, payload, "llm_api_key", "LLM"),
            "base_url": payload.get("llm_base_url"),
            "model": payload.get("llm_model"),
            "batch_size": payload.get("llm_batch_size"),
            "rate_limit": payload.get("llm_rate_limit"),
            "proxy": payload.get("llm_proxy"),
        },
    }


def _next_secret(current: str | None, payload: dict[str, Any], key: str, label: str) -> str | None:
    if key not in payload:
        return current
    replacement = payload.get(key)
    text = replacement.strip() if replacement else ""
    if not text:
        raise ConfigurationError(
            f"{label} provider API key is required",
            code=f"provider.{label.casefold()}_required",
            details={"provider": label.casefold()},
        )
    return text
