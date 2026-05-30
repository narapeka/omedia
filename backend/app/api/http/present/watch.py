from __future__ import annotations

from app.api.http.schemas.watch import WatchSettings, WatchSettingsChild, WatchStatus


def present_watch_settings(config) -> WatchSettings | None:
    if config is None:
        return None
    return WatchSettings(path=config.path, enabled=config.enabled, id=config.id)


def present_watch_status(status) -> WatchStatus:
    return WatchStatus(
        id=status.id,
        label=status.label,
        running=status.running,
        state=status.state,
        last_event=status.current_item_id,
        last_error=status.last_error,
        started_at=status.started_at,
        updated_at=status.updated_at,
    )


def present_watch_settings_child(child) -> WatchSettingsChild:
    return WatchSettingsChild(
        name=child.name,
        path=child.path,
        status=child.status,
        origin_id=child.origin_id,
        media_type=child.media_type,
        candidate_count=child.candidate_count,
        unknown_count=child.unknown_count,
    )
