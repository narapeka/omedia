from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from app.core.error import ConfigurationError
from app.core.path import normalized_path_key
from app.domain.depot import Depot, ResolveMode
from app.domain.media import MediaType
from app.domain.origin import Origin, OriginTrigger
from app.domain.transfer import TransferTrigger
from app.domain.watch import WatchSettings
from app.services.transfer.schedule import validate_cron_schedule


class LocationValidator(Protocol):
    def validate_watch_settings(
        self,
        settings: WatchSettings,
        *,
        origins: Sequence[Origin] = (),
        depots: Sequence[Depot] = (),
    ) -> None:
        ...

    def validate_origin(
        self,
        origin: Origin,
        *,
        watch_settings: WatchSettings | None,
        origins: Sequence[Origin] = (),
        depots: Sequence[Depot] = (),
    ) -> None:
        ...

    def validate_depot(
        self,
        depot: Depot,
        *,
        watch_settings: WatchSettings | None,
        origins: Sequence[Origin] = (),
        depots: Sequence[Depot] = (),
    ) -> None:
        ...


@dataclass(frozen=True)
class ManagedPath:
    label: str
    path: Path
    kind: str
    origin: Origin | None = None


class StrictPathValidator:
    def validate_watch_settings(
        self,
        settings: WatchSettings,
        *,
        origins: Sequence[Origin],
        depots: Sequence[Depot],
    ) -> None:
        _ensure_absolute(settings.path, "WatchSettings")
        _ensure_not_unknown(settings.path, "WatchSettings")
        self._validate_all(settings, origins=origins, depots=depots)

    def validate_origin(
        self,
        origin: Origin,
        *,
        watch_settings: WatchSettings | None,
        origins: Sequence[Origin],
        depots: Sequence[Depot],
    ) -> None:
        _ensure_absolute(origin.path, f"Origin {origin.id}")
        _ensure_not_unknown(origin.path, f"Origin {origin.id}")
        if origin.trigger == OriginTrigger.WATCH:
            if watch_settings is None:
                raise ConfigurationError("Watch Origin requires a configured WatchSettings", code="watch.not_configured")
            _ensure_direct_child(origin.path, watch_settings.path, f"Origin {origin.id}")
        self._validate_all(watch_settings, origins=[*origins, origin], depots=depots)

    def validate_depot(
        self,
        depot: Depot,
        *,
        watch_settings: WatchSettings | None,
        origins: Sequence[Origin],
        depots: Sequence[Depot],
    ) -> None:
        _ensure_absolute(depot.path, f"Depot {depot.id}")
        _ensure_absolute(depot.policy.target_library_path, f"Depot {depot.id} Library")
        _ensure_not_unknown(depot.path, f"Depot {depot.id}")
        _ensure_not_unknown(depot.policy.target_library_path, f"Depot {depot.id} Library")
        self._validate_all(watch_settings, origins=origins, depots=[*depots, depot])

    def _validate_all(
        self,
        watch_settings: WatchSettings | None,
        *,
        origins: Sequence[Origin],
        depots: Sequence[Depot],
    ) -> None:
        if watch_settings is not None:
            _ensure_absolute(watch_settings.path, "WatchSettings")
            _ensure_not_unknown(watch_settings.path, "WatchSettings")
        for origin in origins:
            _ensure_absolute(origin.path, f"Origin {origin.id}")
            _ensure_not_unknown(origin.path, f"Origin {origin.id}")
            if origin.trigger == OriginTrigger.WATCH:
                if watch_settings is None:
                    raise ConfigurationError(
                        f"Watch Origin {origin.id} requires a configured WatchSettings",
                        code="watch.not_configured",
                        details={"origin_id": origin.id, "origin_name": origin.name},
                    )
                _ensure_direct_child(origin.path, watch_settings.path, f"Origin {origin.id}")
        for depot in depots:
            _ensure_absolute(depot.path, f"Depot {depot.id}")
            _ensure_absolute(depot.policy.target_library_path, f"Depot {depot.id} Library")
            _ensure_not_unknown(depot.path, f"Depot {depot.id}")
            _ensure_not_unknown(depot.policy.target_library_path, f"Depot {depot.id} Library")
            _ensure_transfer_policy(depot)

        managed = _managed_paths(watch_settings, origins=origins, depots=depots)
        for index, left in enumerate(managed):
            for right in managed[index + 1 :]:
                if _is_watch_settings_child_exception(left, right):
                    continue
                if _paths_overlap(left.path, right.path):
                    raise ConfigurationError(
                        f"Managed paths overlap: {left.label} ({left.path}) and {right.label} ({right.path})",
                        code="path.overlap",
                        details={
                            "left_label": left.label,
                            "left_path": str(left.path),
                            "right_label": right.label,
                            "right_path": str(right.path),
                        },
                    )


class LocationService:
    def __init__(self, store, validator: LocationValidator | None = None):
        self.store = store
        self.validator = validator or StrictPathValidator()

    def get_watch_settings(self) -> WatchSettings | None:
        return self.store.get_watch_settings()

    def save_watch_settings(self, settings: WatchSettings) -> WatchSettings:
        current = self.store.get_watch_settings()
        origins = self.store.list_origins()
        depots = self.store.list_depots()
        root_changed = current is not None and normalized_path_key(current.path) != normalized_path_key(settings.path)
        if root_changed:
            saved = replace(settings, enabled=False)
            retained_origins = [origin for origin in origins if origin.trigger != OriginTrigger.WATCH]
            self.validator.validate_watch_settings(
                saved,
                origins=retained_origins,
                depots=depots,
            )
            self.store.replace_watch_root(saved)
            return saved

        self.validator.validate_watch_settings(
            settings,
            origins=origins,
            depots=depots,
        )
        self.store.save_watch_settings(settings)
        return settings

    def list_origins(self) -> list[Origin]:
        return self.store.list_origins()

    def get_origin(self, origin_id: str) -> Origin:
        origin = self.store.get_origin(origin_id)
        if origin is None:
            raise ConfigurationError(f"Unknown Origin: {origin_id}", code="origin.unknown", details={"origin_id": origin_id})
        return origin

    def save_origin(self, origin: Origin) -> Origin:
        origin = replace(origin, name=_clean_name(origin.name, "Origin"))
        origins = [item for item in self.store.list_origins() if item.id != origin.id]
        depots = self.store.list_depots()
        target_depot = self.store.get_depot(origin.policy.target_depot_id)
        if target_depot is None:
            raise ConfigurationError(
                f"Origin {origin.name} references unknown Depot: {origin.policy.target_depot_id}",
                code="origin.unknown_depot",
                details={"origin_id": origin.id, "origin_name": origin.name, "depot_id": origin.policy.target_depot_id},
            )
        if target_depot.media_type != origin.media_type:
            raise ConfigurationError(
                f"Origin {origin.name} media type must match target Depot {target_depot.name}",
                code="origin.depot_media_mismatch",
                details={
                    "origin_id": origin.id,
                    "origin_name": origin.name,
                    "depot_id": target_depot.id,
                    "depot_name": target_depot.name,
                    "origin_media_type": origin.media_type.value,
                    "depot_media_type": target_depot.media_type.value,
                },
            )
        _ensure_unique_name(origin.name, origins, "Origin")
        if origin.policy.organize_rule_id and self.store.get_organize_rule(origin.policy.organize_rule_id) is None:
            raise ConfigurationError(
                f"Origin {origin.name} references unknown Organize rule: {origin.policy.organize_rule_id}",
                code="origin.unknown_organize_rule",
                details={"origin_id": origin.id, "origin_name": origin.name, "rule_id": origin.policy.organize_rule_id},
            )
        self.validator.validate_origin(
            origin,
            watch_settings=self.store.get_watch_settings(),
            origins=origins,
            depots=depots,
        )
        self.store.save_origin(origin)
        return origin

    def delete_origin(self, origin_id: str) -> bool:
        return self.store.delete_origin(origin_id)

    def list_depots(self) -> list[Depot]:
        return self.store.list_depots()

    def get_depot(self, depot_id: str) -> Depot:
        depot = self.store.get_depot(depot_id)
        if depot is None:
            raise ConfigurationError(f"Unknown Depot: {depot_id}", code="depot.unknown", details={"depot_id": depot_id})
        return depot

    def save_depot(self, depot: Depot) -> Depot:
        depot = replace(depot, name=_clean_name(depot.name, "Depot"))
        if depot.media_type == MediaType.MOVIE and depot.resolve_mode != ResolveMode.FULL:
            depot = replace(depot, resolve_mode=ResolveMode.FULL)
        depots = [item for item in self.store.list_depots() if item.id != depot.id]
        _ensure_unique_name(depot.name, depots, "Depot")
        if depot.policy.transfer_rule_id and self.store.get_transfer_rule(depot.policy.transfer_rule_id) is None:
            raise ConfigurationError(
                f"Depot {depot.name} references unknown Transfer rule: {depot.policy.transfer_rule_id}",
                code="depot.unknown_transfer_rule",
                details={"depot_id": depot.id, "depot_name": depot.name, "rule_id": depot.policy.transfer_rule_id},
            )
        self.validator.validate_depot(
            depot,
            watch_settings=self.store.get_watch_settings(),
            origins=self.store.list_origins(),
            depots=depots,
        )
        self.store.save_depot(depot)
        return depot

    def delete_depot(self, depot_id: str) -> bool:
        depot = self.get_depot(depot_id)
        used_by = [
            origin.name
            for origin in self.store.list_origins()
            if origin.policy.target_depot_id == depot.id
        ]
        if used_by:
            raise ConfigurationError(
                f"Depot {depot.name} is still used by Origin(s): {', '.join(sorted(used_by))}",
                code="depot.used_by_origin",
                details={"depot_id": depot.id, "depot_name": depot.name, "origins": sorted(used_by), "count": len(used_by)},
            )
        return self.store.delete_depot(depot_id)


def _managed_paths(
    watch_settings: WatchSettings | None,
    *,
    origins: Sequence[Origin],
    depots: Sequence[Depot],
) -> list[ManagedPath]:
    paths: list[ManagedPath] = []
    if watch_settings is not None:
        paths.append(ManagedPath("WatchSettings", watch_settings.path, "watch_settings"))
    paths.extend(ManagedPath(f"Origin {origin.id}", origin.path, "origin", origin=origin) for origin in origins)
    for depot in depots:
        paths.append(ManagedPath(f"Depot {depot.id}", depot.path, "depot"))
        paths.append(ManagedPath(f"Depot {depot.id} Library", depot.policy.target_library_path, "library"))
    return paths


def _ensure_absolute(path: Path, label: str) -> None:
    if not path.is_absolute():
        raise ConfigurationError(
            f"{label} path must be absolute: {path}",
            code="path.not_absolute",
            details={"label": label, "path": str(path)},
        )


def _ensure_not_unknown(path: Path, label: str) -> None:
    if any(part.casefold() == ".unknown" for part in path.parts):
        raise ConfigurationError(
            f"{label} cannot use reserved .unknown path: {path}",
            code="path.reserved_unknown",
            details={"label": label, "path": str(path)},
        )


def _ensure_direct_child(path: Path, parent: Path, label: str) -> None:
    if normalized_path_key(path.parent) != normalized_path_key(parent):
        raise ConfigurationError(
            f"{label} must be exactly one direct child below WatchSettings",
            code="path.watch_direct_child",
            details={"label": label, "path": str(path), "watch_path": str(parent)},
        )


def _ensure_transfer_policy(depot: Depot) -> None:
    if depot.policy.trigger == TransferTrigger.SCHEDULED and not (depot.policy.schedule or "").strip():
        raise ConfigurationError(
            f"Depot {depot.id} schedule is required when transfer trigger is scheduled",
            code="depot.schedule_required",
            details={"depot_id": depot.id, "depot_name": depot.name},
        )
    if depot.policy.trigger == TransferTrigger.SCHEDULED:
        validate_cron_schedule((depot.policy.schedule or "").strip())


def _clean_name(value: str, object_type: str) -> str:
    name = (value or "").strip()
    if not name:
        raise ConfigurationError(f"{object_type} name is required", code="name.required", details={"object": object_type})
    return name


def _ensure_unique_name(name: str, existing: Sequence[Origin] | Sequence[Depot], object_type: str) -> None:
    normalized = name.casefold()
    if any(item.name.strip().casefold() == normalized for item in existing):
        raise ConfigurationError(
            f"{object_type} name already exists: {name}",
            code="name.duplicate",
            details={"object": object_type, "name": name},
        )


def _is_watch_settings_child_exception(left: ManagedPath, right: ManagedPath) -> bool:
    if left.kind == "watch_settings" and _is_watch_origin_direct_child(right, left.path):
        return True
    if right.kind == "watch_settings" and _is_watch_origin_direct_child(left, right.path):
        return True
    return False


def _is_watch_origin_direct_child(entry: ManagedPath, watch_settings_path: Path) -> bool:
    return (
        entry.kind == "origin"
        and entry.origin is not None
        and entry.origin.trigger == OriginTrigger.WATCH
        and normalized_path_key(entry.path.parent) == normalized_path_key(watch_settings_path)
    )


def _paths_overlap(left: Path, right: Path) -> bool:
    left_norm = normalized_path_key(left)
    right_norm = normalized_path_key(right)
    return left_norm == right_norm or left_norm.startswith(f"{right_norm}/") or right_norm.startswith(f"{left_norm}/")
