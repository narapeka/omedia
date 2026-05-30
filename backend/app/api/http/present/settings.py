from __future__ import annotations

from app.api.http.schemas.config import (
    MediaExtensionSettings,
    OrganizeSettings,
    ProviderStatus,
    WatchRuntimeSettings,
)


def present_media_settings(policy) -> MediaExtensionSettings:
    return MediaExtensionSettings(
        video=sorted(policy.video),
        subtitle=sorted(policy.subtitle),
        sidecar=sorted(policy.sidecar),
    )


def present_watch_runtime_settings(settings) -> WatchRuntimeSettings:
    return WatchRuntimeSettings(
        poll_interval_seconds=settings.poll_interval_seconds,
        stability_debounce_seconds=settings.stability_debounce_seconds,
    )


def present_organize_settings(settings) -> OrganizeSettings:
    return OrganizeSettings(
        extensions=present_media_settings(settings.extensions),
        min_non_subtitle_file_size_mb=settings.min_non_subtitle_file_size_mb or 0,
    )


def present_provider_status(providers) -> ProviderStatus:
    return ProviderStatus(
        tmdb_api_key=providers.tmdb_api_key,
        tmdb_base_url=providers.tmdb_base_url,
        tmdb_rate_limit=providers.tmdb_rate_limit,
        tmdb_proxy=providers.tmdb_proxy,
        llm_api_key=providers.llm_api_key,
        llm_base_url=providers.llm_base_url,
        llm_model=providers.llm_model,
        llm_batch_size=providers.llm_batch_size,
        llm_rate_limit=providers.llm_rate_limit,
        llm_proxy=providers.llm_proxy,
    )
