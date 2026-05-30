from __future__ import annotations

from dataclasses import dataclass
import os
import shutil
import sys
from pathlib import Path

from app.core.error import ConfigurationError
from app.services.inventory.service import InventoryService
from app.services.organize.session import SessionBook
from app.services.config.location import LocationService
from app.services.config.service import ConfigurationService
from app.services.activity.query import ActivityQueryService
from app.services.watch.service import WatchService
from app.services.config.rule import RuleBook
from app.services.depot.service import DepotService
from app.services.transfer.schedule import TransferService
from app.services.admin.service import AdminService
from app.infra.log.app import app_log
from app.infra.db.store import Store
from app.services.depot.lock import DepotLockRegistry
from app.services.activity.recorder import ActivityRecorder
from app.services.organize.execute import OrganizeExecutor
from app.services.organize.service import OrganizeService
from app.services.transfer.worker import TransferWorker
from app.boot.background import BackgroundRuntime
from app.boot.match import MatchRuntime as _MatchRuntime
from app.boot.refresh import RuntimeRefresh
from app.boot.settings import load_startup_settings
from app.services.config.settings import SettingsFile
from app.services.config.values import StartupSettings


@dataclass(frozen=True)
class RuntimeSettings:
    common_path: Path
    db_path: Path


@dataclass
class RuntimeContext:
    """Concrete runtime shared by CLI now and API/Web UI later."""

    common_path: Path
    db_path: Path
    startup_settings: StartupSettings
    store: Store
    locations: LocationService
    configuration: ConfigurationService
    settings_file: SettingsFile
    admin_service: AdminService
    organize_pipeline: OrganizeService
    inventory: InventoryService
    organize_sessions: SessionBook
    activity: ActivityQueryService
    rules: RuleBook
    depot_service: DepotService
    depot_locks: DepotLockRegistry
    activity_recorder: ActivityRecorder
    organizer: OrganizeExecutor
    transfer_worker: TransferWorker
    watch_automation: WatchService
    transfer_service: TransferService
    background: BackgroundRuntime
    match: _MatchRuntime

    def start_automations(self) -> None:
        self.background.start()

    def stop_automations(self) -> None:
        self.background.stop()

    def close(self) -> None:
        try:
            self.stop_automations()
        finally:
            self.store.close()

    def replace_match(self, match: _MatchRuntime) -> None:
        self.match = match

    @property
    def transfer_automation(self) -> TransferService:
        return self.transfer_service


def resolve_runtime_settings(
    *,
    db_path: str | Path | None = None,
    cwd: Path | None = None,
) -> RuntimeSettings:
    data_dir = default_data_dir(cwd=cwd)
    return RuntimeSettings(
        common_path=data_dir / "common.yaml",
        db_path=Path(db_path or data_dir / "omedia.sqlite3"),
    )


def default_data_dir(*, cwd: Path | None = None) -> Path:
    configured = os.environ.get("OMEDIA_DATA_DIR")
    if configured:
        return Path(configured)
    if _is_frozen_windows():
        return Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "omedia" / "data"
    current = cwd or Path.cwd()
    if current.name == "backend":
        return current.parent / "data"
    return current / "data"


def default_data_path(filename: str, *, cwd: Path | None = None) -> Path:
    return default_data_dir(cwd=cwd) / filename


def ensure_common_config(common_path: str | Path) -> None:
    target = Path(common_path)
    if target.exists():
        return
    source = find_common_example_path()
    if source is None:
        raise ConfigurationError("Configuration file not found and common.example.yaml is unavailable")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def find_common_example_path() -> Path | None:
    for candidate in _common_example_candidates():
        if candidate.exists():
            return candidate
    return None


def create_runtime_context_from_settings(settings: RuntimeSettings) -> RuntimeContext:
    return create_runtime_context(
        common_path=settings.common_path,
        db_path=settings.db_path,
    )


def create_runtime_context(
    *,
    common_path: str | Path,
    db_path: str | Path,
) -> RuntimeContext:
    ensure_common_config(common_path)
    app_log.configure(Path(db_path).parent / "logs")
    store = Store(db_path)
    store.initialize()
    startup_settings = load_startup_settings(
        common_path=common_path,
    )
    organize_settings = startup_settings.organize
    extensions = organize_settings.extensions

    locations = LocationService(store)
    settings_file = SettingsFile(Path(common_path), startup_settings)
    inventory = InventoryService(
        extensions,
        min_non_subtitle_file_size_bytes=organize_settings.min_non_subtitle_file_size_bytes,
    )
    organize_sessions = SessionBook()
    activity = ActivityQueryService(store)
    rules = RuleBook(store=store)
    depot_locks = DepotLockRegistry()
    activity_recorder = ActivityRecorder(store)
    depot_service = DepotService(
        locks=depot_locks,
        activity=activity_recorder,
        store=store,
        extensions=extensions,
        sidecar_extensions=frozenset(),
    )
    organizer = OrganizeExecutor(
        locks=depot_locks,
        activity=activity_recorder,
        sidecar_extensions=extensions.sidecar,
        subtitle_extensions=extensions.subtitle,
        extensions=extensions,
        min_non_subtitle_file_size_bytes=organize_settings.min_non_subtitle_file_size_bytes,
    )
    transfer_worker = TransferWorker(
        store=store,
        locks=depot_locks,
        activity=activity_recorder,
        extensions=extensions,
    )
    match = _MatchRuntime(startup_settings, store=store)
    watch_automation = WatchService(
        configuration=locations,
        matcher=match,
        organizer=organizer,
        activity=activity_recorder,
        inventory=inventory,
        extensions=extensions,
        min_non_subtitle_file_size_bytes=organize_settings.min_non_subtitle_file_size_bytes,
        poll_interval_seconds=startup_settings.watch.poll_interval_seconds,
        debounce_seconds=startup_settings.watch.stability_debounce_seconds,
    )
    transfer_service = TransferService(
        configuration=locations,
        worker=transfer_worker,
    )
    refresh = RuntimeRefresh(None)
    configuration = ConfigurationService(
        locations=locations,
        settings=settings_file,
        effects=refresh,
        rules=rules,
        store=store,
        sessions=organize_sessions,
        watch=watch_automation,
        depots=depot_service,
    )
    admin_service = AdminService(
        store=store,
        settings=settings_file,
        effects=refresh,
        rules=rules,
        validator=locations.validator,
        match=match,
    )
    organize_pipeline = OrganizeService(
        configuration=locations,
        sessions=organize_sessions,
        settings=settings_file,
        match=match,
        organizer=organizer,
        activity=activity_recorder,
        store=store,
    )
    background = BackgroundRuntime([watch_automation, transfer_service])

    runtime = RuntimeContext(
        common_path=Path(common_path),
        db_path=Path(db_path),
        startup_settings=startup_settings,
        store=store,
        locations=locations,
        configuration=configuration,
        settings_file=settings_file,
        admin_service=admin_service,
        organize_pipeline=organize_pipeline,
        inventory=inventory,
        organize_sessions=organize_sessions,
        activity=activity,
        rules=rules,
        depot_service=depot_service,
        depot_locks=depot_locks,
        activity_recorder=activity_recorder,
        organizer=organizer,
        transfer_worker=transfer_worker,
        watch_automation=watch_automation,
        transfer_service=transfer_service,
        background=background,
        match=match,
    )
    object.__setattr__(refresh, "runtime", runtime)
    return runtime


def _common_example_candidates() -> tuple[Path, ...]:
    bundle_root = Path(getattr(sys, "_MEIPASS", ""))
    return (
        bundle_root / "data" / "common.example.yaml",
        Path.cwd() / "data" / "common.example.yaml",
        Path(__file__).resolve().parents[3] / "data" / "common.example.yaml",
    )


def _is_frozen_windows() -> bool:
    return bool(getattr(sys, "frozen", False)) and os.name == "nt"

