from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.core.error import ConfigurationError
from app.domain.depot import Depot
from app.domain.origin import Origin
from app.domain.rule import OrganizeRule, TransferRule
from app.domain.watch import WatchSettings
from app.infra.log.app import app_log
from app.services.admin.payload import (
    depot_from_data,
    organize_rule_from_data,
    origin_from_data,
    provider_config_payload,
    transfer_rule_from_data,
    watch_settings_from_data,
)
from app.services.config.location import LocationValidator
from app.services.config.rule import RuleBook
from app.services.config.settings import SettingsFile
from app.services.config.values import parse_provider_settings


def restore_config_backup(
    store,
    settings: SettingsFile,
    validator: LocationValidator,
    rules: RuleBook,
    backup: Mapping[str, Any],
):
    return ConfigRestore(store, settings, validator, rules, backup).apply()


@dataclass(frozen=True)
class ConfigRestorePayload:
    watch_settings: WatchSettings | None
    origins: list[Origin]
    depots: list[Depot]
    organize_rules: list[OrganizeRule]
    transfer_rules: list[TransferRule]

    @classmethod
    def from_backup(cls, backup: Mapping[str, Any]) -> ConfigRestorePayload:
        return cls(
            watch_settings=watch_settings_from_data(backup["watch_settings"]) if backup.get("watch_settings") else None,
            origins=[origin_from_data(origin) for origin in backup["origins"]],
            depots=[depot_from_data(depot) for depot in backup["depots"]],
            organize_rules=[organize_rule_from_data(rule) for rule in backup["organize_rules"]],
            transfer_rules=[transfer_rule_from_data(rule) for rule in backup["transfer_rules"]],
        )

    def store_args(self) -> dict[str, Any]:
        return {
            "watch_settings": self.watch_settings,
            "origins": self.origins,
            "depots": self.depots,
            "organize_rules": self.organize_rules,
            "transfer_rules": self.transfer_rules,
        }

    def validate(self, validator: LocationValidator, rules: RuleBook) -> None:
        ensure_unique_ids(self.origins, "Origin")
        ensure_unique_ids(self.depots, "Depot")
        ensure_unique_ids(self.organize_rules, "Organize rule")
        ensure_unique_ids(self.transfer_rules, "Transfer rule")
        ensure_required_unique_names(self.origins, "Origin")
        ensure_required_unique_names(self.depots, "Depot")
        ensure_required_unique_names(self.organize_rules, "Organize rule")
        ensure_required_unique_names(self.transfer_rules, "Transfer rule")

        depot_by_id = {depot.id: depot for depot in self.depots}
        organize_rule_ids = {rule.id for rule in self.organize_rules}
        transfer_rule_ids = {rule.id for rule in self.transfer_rules}
        for origin in self.origins:
            target_depot = depot_by_id.get(origin.policy.target_depot_id)
            if target_depot is None:
                raise ConfigurationError(f"Origin {origin.name} references unknown Depot: {origin.policy.target_depot_id}")
            if target_depot.media_type != origin.media_type:
                raise ConfigurationError(f"Origin {origin.name} media type must match target Depot {target_depot.name}")
            if origin.policy.organize_rule_id and origin.policy.organize_rule_id not in organize_rule_ids:
                raise ConfigurationError(f"Origin {origin.name} references unknown Organize rule: {origin.policy.organize_rule_id}")
        for depot in self.depots:
            if depot.policy.transfer_rule_id and depot.policy.transfer_rule_id not in transfer_rule_ids:
                raise ConfigurationError(f"Depot {depot.name} references unknown Transfer rule: {depot.policy.transfer_rule_id}")

        if self.watch_settings:
            validator.validate_watch_settings(self.watch_settings, origins=self.origins, depots=self.depots)
        for origin in self.origins:
            validator.validate_origin(
                origin,
                watch_settings=self.watch_settings,
                origins=[item for item in self.origins if item.id != origin.id],
                depots=self.depots,
            )
        for depot in self.depots:
            validator.validate_depot(
                depot,
                watch_settings=self.watch_settings,
                origins=self.origins,
                depots=[item for item in self.depots if item.id != depot.id],
            )
        for rule in self.organize_rules:
            rules.organize_engine.validate(rule)
        for rule in self.transfer_rules:
            rules.transfer_engine.validate(rule)


class ConfigRestore:
    def __init__(
        self,
        store,
        settings: SettingsFile,
        validator: LocationValidator,
        rules: RuleBook,
        backup: Mapping[str, Any],
    ) -> None:
        self.store = store
        self.settings = settings
        self.validator = validator
        self.rules = rules
        self.backup = backup
        self.payload = ConfigRestorePayload.from_backup(backup)
        self.providers = parse_provider_settings(provider_config_payload(backup["providers"]))
        self.providers.require_identify()

    def apply(self):
        self.payload.validate(self.validator, self.rules)
        result = self.store.replace_admin_backup(**self.payload.store_args())
        self.settings.write_providers(self.providers)
        self.settings.write_organize(self.backup["organize"])
        if self.backup.get("watch_runtime") is not None:
            self.settings.write_watch(self.backup["watch_runtime"])
        app_log.warning(
            "admin.config",
            "Configuration restored and history cleared",
            activity_events=result.cleared.activity_events,
            transfer_jobs=result.cleared.transfer_jobs,
        )
        return result


def ensure_unique_ids(items: list[Any], object_type: str) -> None:
    seen: set[str] = set()
    for item in items:
        if item.id in seen:
            raise ConfigurationError(f"{object_type} ID already exists in backup: {item.id}")
        seen.add(item.id)


def ensure_required_unique_names(items: list[Any], object_type: str) -> None:
    seen: set[str] = set()
    for item in items:
        name = (item.name or "").strip()
        if not name:
            raise ConfigurationError(f"{object_type} name is required")
        normalized = name.casefold()
        if normalized in seen:
            raise ConfigurationError(f"{object_type} name already exists: {name}")
        seen.add(normalized)
