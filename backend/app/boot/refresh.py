from __future__ import annotations

from app.boot.match import MatchRuntime
from app.services.config.values import OrganizeSettings, ProviderSettings, WatchRuntimeSettings


def refresh_provider_settings(runtime) -> None:
    match = MatchRuntime(runtime.startup_settings, store=runtime.store)
    runtime.replace_match(match)
    runtime.watch_automation.update_matcher(match)
    runtime.organize_pipeline.update_matcher(match)
    runtime.admin_service.update_matcher(match)


def apply_organize_settings(runtime, settings: OrganizeSettings) -> None:
    runtime.startup_settings.organize = settings
    extensions = settings.extensions
    runtime.inventory.extensions = extensions
    runtime.inventory.min_non_subtitle_file_size_bytes = settings.min_non_subtitle_file_size_bytes
    runtime.depot_service.extensions = extensions
    runtime.transfer_worker.extensions = extensions
    runtime.organizer.update_media_policy(
        extensions=extensions,
        sidecar_extensions=extensions.sidecar,
        subtitle_extensions=extensions.subtitle,
        min_non_subtitle_file_size_bytes=settings.min_non_subtitle_file_size_bytes,
    )
    refresh_provider_settings(runtime)
    runtime.watch_automation.update_extensions(extensions)
    runtime.watch_automation.update_min_non_subtitle_file_size(settings.min_non_subtitle_file_size_bytes)


def apply_watch_runtime_settings(runtime, settings: WatchRuntimeSettings) -> None:
    runtime.startup_settings.watch = settings
    runtime.watch_automation.update_runtime_settings(
        poll_interval_seconds=settings.poll_interval_seconds,
        debounce_seconds=settings.stability_debounce_seconds,
    )


class RuntimeRefresh:
    def __init__(self, runtime) -> None:
        self.runtime = runtime

    def providers_changed(self, settings: ProviderSettings) -> None:
        refresh_provider_settings(self.runtime)

    def organize_changed(self, settings: OrganizeSettings) -> None:
        apply_organize_settings(self.runtime, settings)

    def watch_changed(self, settings: WatchRuntimeSettings) -> None:
        apply_watch_runtime_settings(self.runtime, settings)

    def configuration_restored(self) -> None:
        self.after_restore()

    def after_restore(self) -> None:
        refresh_provider_settings(self.runtime)
        policy = self.runtime.startup_settings.organize.extensions
        self.runtime.inventory.extensions = policy
        self.runtime.inventory.min_non_subtitle_file_size_bytes = self.runtime.startup_settings.organize.min_non_subtitle_file_size_bytes
        self.runtime.depot_service.extensions = policy
        self.runtime.transfer_worker.extensions = policy
        self.runtime.organizer.update_media_policy(
            extensions=policy,
            sidecar_extensions=policy.sidecar,
            subtitle_extensions=policy.subtitle,
            min_non_subtitle_file_size_bytes=self.runtime.startup_settings.organize.min_non_subtitle_file_size_bytes,
        )
        self.runtime.watch_automation.update_extensions(policy)
        self.runtime.watch_automation.update_min_non_subtitle_file_size(self.runtime.startup_settings.organize.min_non_subtitle_file_size_bytes)
        self.runtime.watch_automation.update_runtime_settings(
            poll_interval_seconds=self.runtime.startup_settings.watch.poll_interval_seconds,
            debounce_seconds=self.runtime.startup_settings.watch.stability_debounce_seconds,
        )
        self.runtime.watch_automation.refresh()
