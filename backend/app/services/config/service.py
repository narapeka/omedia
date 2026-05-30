from __future__ import annotations

from dataclasses import dataclass

from app.core.error import ConfigurationError
from app.domain.depot import Depot
from app.domain.origin import Origin, OriginTrigger
from app.domain.transfer import TransferTrigger
from app.domain.watch import WatchSettings
from app.services.config.location import LocationService
from app.services.config.rule import RuleBook
from app.services.config.settings import SettingsFile, SettingsRuntimeEffects


@dataclass(frozen=True)
class ConfigurationHealth:
    ok: bool
    database: bool
    config_loaded: bool
    origins: int
    depots: int
    organize_rules: int
    transfer_rules: int
    watched_folders: int
    scheduled_transfers: int


class ConfigurationService:
    def __init__(
        self,
        *,
        locations: LocationService,
        settings: SettingsFile,
        effects: SettingsRuntimeEffects,
        rules: RuleBook,
        store,
        sessions,
        watch,
        depots,
    ) -> None:
        self.locations = locations
        self.settings = settings
        self.effects = effects
        self.rules = rules
        self.store = store
        self.sessions = sessions
        self.watch = watch
        self.depots = depots

    @property
    def validator(self):
        return self.locations.validator

    def health(self) -> ConfigurationHealth:
        database = True
        try:
            self.store.ping()
        except Exception:
            database = False
        origins = self.locations.list_origins()
        manual_origins = [origin for origin in origins if origin.trigger == OriginTrigger.MANUAL]
        depots = self.locations.list_depots()
        return ConfigurationHealth(
            ok=database,
            database=database,
            config_loaded=self.settings is not None,
            origins=len(manual_origins),
            depots=len(depots),
            organize_rules=len(self.rules.list_organize()),
            transfer_rules=len(self.rules.list_transfer()),
            watched_folders=sum(1 for origin in origins if origin.trigger == OriginTrigger.WATCH),
            scheduled_transfers=sum(1 for depot in depots if depot.policy.trigger == TransferTrigger.SCHEDULED),
        )

    def providers(self):
        return self.settings.providers

    def save_provider_settings(self, payload: dict) -> object:
        providers = self.settings.save_provider_settings(payload)
        self.effects.providers_changed(providers)
        return providers

    def organize_settings(self):
        return self.settings.organize

    def save_organize_settings(self, payload: dict) -> object:
        settings = self.settings.save_organize_settings(payload)
        self.effects.organize_changed(settings)
        return settings

    def watch_runtime_settings(self):
        return self.settings.watch

    def save_watch_runtime_settings(self, payload: dict) -> object:
        settings = self.settings.save_watch_runtime_settings(payload)
        self.effects.watch_changed(settings)
        return settings

    def get_watch_settings(self) -> WatchSettings | None:
        return self.locations.get_watch_settings()

    def save_watch_settings(self, settings: WatchSettings) -> WatchSettings:
        saved = self.locations.save_watch_settings(settings)
        self.watch.refresh()
        return saved

    def list_origins(self) -> list[Origin]:
        return self.locations.list_origins()

    def get_origin(self, origin_id: str) -> Origin:
        return self.locations.get_origin(origin_id)

    def save_origin(self, origin: Origin) -> Origin:
        _ensure_watch_origin_directory(self.locations, origin)
        saved = self.locations.save_origin(origin)
        self.watch.update_origin(saved)
        return saved

    def delete_origin(self, origin_id: str) -> bool:
        origin = self.locations.get_origin(origin_id)
        active_sessions = [
            session
            for session in self.sessions.active_sessions()
            if session.origin_id == origin.id
        ]
        if active_sessions:
            raise ConfigurationError(
                f"Origin {origin.name} has active OrganizeSession",
                code="origin.active_session",
                details={"origin_id": origin.id, "origin_name": origin.name, "session_ids": [session.id for session in active_sessions]},
            )
        deleted = self.locations.delete_origin(origin_id)
        self.watch.refresh()
        return deleted

    def list_depots(self) -> list[Depot]:
        return self.locations.list_depots()

    def get_depot(self, depot_id: str) -> Depot:
        return self.locations.get_depot(depot_id)

    def save_depot(self, depot: Depot) -> Depot:
        return self.locations.save_depot(depot)

    def delete_depot(self, depot_id: str) -> bool:
        depot = self.locations.get_depot(depot_id)
        active_sessions = [
            session
            for session in self.sessions.active_sessions()
            if session.policy.target_depot_id == depot.id
        ]
        if active_sessions:
            raise ConfigurationError(
                f"Depot {depot.name} has active OrganizeSession",
                code="depot.active_session",
                details={"depot_id": depot.id, "depot_name": depot.name, "session_ids": [session.id for session in active_sessions]},
            )
        active_job = self.store.active_transfer_job_for_depot(depot.id)
        if active_job is not None:
            raise ConfigurationError(
                f"Depot {depot.name} has active TransferJob",
                code="depot.active_transfer",
                details={"depot_id": depot.id, "depot_name": depot.name, "transfer_job_id": active_job.id},
            )
        return self.locations.delete_depot(depot_id)

    def transfer_history(self, depot: Depot):
        return self.depots.transfer_history(depot)

    def rule_references(self):
        return self.rules.references()

    def list_organize_rules(self):
        return self.rules.list_organize()

    def save_organize_rule(self, rule):
        return self.rules.save_organize(rule)

    def preview_organize_rule(self, rule, *, tmdb: dict, relative_path):
        return self.rules.preview_organize(rule, tmdb=tmdb, relative_path=relative_path)

    def delete_organize_rule(self, rule_id: str) -> bool:
        return self.rules.delete_organize(rule_id)

    def list_transfer_rules(self):
        return self.rules.list_transfer()

    def save_transfer_rule(self, rule):
        return self.rules.save_transfer(rule)

    def preview_transfer_rule_path(self, rule, *, relative_path):
        return self.rules.preview_transfer_path(rule, relative_path=relative_path)

    def delete_transfer_rule(self, rule_id: str) -> bool:
        return self.rules.delete_transfer(rule_id)


def _ensure_watch_origin_directory(locations: LocationService, origin: Origin) -> None:
    if origin.trigger != OriginTrigger.WATCH:
        return
    watch_settings = locations.get_watch_settings()
    origins = [item for item in locations.list_origins() if item.id != origin.id]
    locations.validator.validate_origin(
        origin,
        watch_settings=watch_settings,
        origins=origins,
        depots=locations.list_depots(),
    )
    if not origin.path.parent.exists() or not origin.path.parent.is_dir():
        raise ConfigurationError(
            f"WatchSettings folder must exist before creating Watch Origin child: {origin.path.parent}",
            code="watch.root_missing",
            details={"path": str(origin.path.parent), "origin_id": origin.id, "origin_name": origin.name},
        )
    try:
        origin.path.mkdir(exist_ok=True)
    except OSError as exc:
        raise ConfigurationError(
            f"Could not create Watch Origin folder: {origin.path}",
            code="watch.origin_create_failed",
            details={"path": str(origin.path), "origin_id": origin.id, "origin_name": origin.name},
        ) from exc
    if not origin.path.is_dir():
        raise ConfigurationError(
            f"Watch Origin path is not a directory: {origin.path}",
            code="watch.origin_not_directory",
            details={"path": str(origin.path), "origin_id": origin.id, "origin_name": origin.name},
        )
