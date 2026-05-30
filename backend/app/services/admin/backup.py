from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.infra.log.app import app_log
from app.services.admin.payload import (
    depot_data,
    origin_data,
    organize_rule_data,
    transfer_rule_data,
    watch_settings_data,
)
from app.services.config.settings import SettingsFile, organize_settings_data, provider_common_data, watch_runtime_data


def build_config_backup(store, settings: SettingsFile) -> dict[str, Any]:
    return ConfigBackup(store, settings).build()


class ConfigBackup:
    def __init__(self, store, settings: SettingsFile) -> None:
        self.store = store
        self.settings = settings

    def build(self) -> dict[str, Any]:
        snapshot = self.store.export_admin_backup()
        backup = {
            "format": "omedia-config-backup",
            "version": 2,
            "exported_at": datetime.now(timezone.utc),
            "organize": organize_settings_data(self.settings.organize),
            "providers": provider_common_data(self.settings.providers),
            "watch_runtime": watch_runtime_data(self.settings.watch),
            "watch_settings": watch_settings_data(snapshot.watch_settings) if snapshot.watch_settings else None,
            "origins": [origin_data(origin) for origin in snapshot.origins],
            "depots": [depot_data(depot) for depot in snapshot.depots],
            "organize_rules": [organize_rule_data(rule) for rule in snapshot.organize_rules],
            "transfer_rules": [transfer_rule_data(rule) for rule in snapshot.transfer_rules],
        }
        app_log.info("admin.config", "Configuration backup created")
        return backup
