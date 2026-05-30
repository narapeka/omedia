from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from app.infra.log.app import app_log
from app.services.admin.backup import build_config_backup
from app.services.admin.restore import restore_config_backup
from app.services.config.rule import RuleBook
from app.services.config.location import LocationValidator
from app.services.config.settings import SettingsFile, SettingsRuntimeEffects


class AdminService:
    def __init__(
        self,
        *,
        store,
        settings: SettingsFile,
        effects: SettingsRuntimeEffects,
        rules: RuleBook,
        validator: LocationValidator,
        match,
    ) -> None:
        self.store = store
        self.settings = settings
        self.effects = effects
        self.rules = rules
        self.validator = validator
        self.match = match

    def update_matcher(self, match) -> None:
        self.match = match

    def clear_tmdb_cache(self) -> int:
        deleted_entries = self.match.clear_tmdb_cache() or 0
        app_log.info("admin.tmdb", "TMDB cache cleared", deleted_entries=deleted_entries)
        return deleted_entries

    def prune_activity(self, older_than_days: int):
        cutoff = _cutoff_before(older_than_days)
        deleted = self.store.delete_activity_events_before(cutoff)
        app_log.info("admin.activity", "Activity events pruned", older_than_days=older_than_days, deleted_events=deleted)
        return cutoff, deleted

    def prune_transfer(self, older_than_days: int):
        cutoff = _cutoff_before(older_than_days)
        counts = self.store.prune_transfer_history_before(cutoff)
        app_log.info(
            "admin.transfer",
            "Transfer job history pruned",
            older_than_days=older_than_days,
            deleted_jobs=counts.deleted_jobs,
        )
        return cutoff, counts

    def backup_config(self) -> dict[str, Any]:
        return build_config_backup(self.store, self.settings)

    def restore_config(self, backup: Mapping[str, Any]):
        result = restore_config_backup(
            self.store,
            self.settings,
            self.validator,
            self.rules,
            backup,
        )
        self.effects.configuration_restored()
        return result


def _cutoff_before(older_than_days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=older_than_days)
