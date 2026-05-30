from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from watchfiles import watch

from app.core.path import normalized_path_key
from app.core.error import ConfigurationError
from app.domain.media import MediaExtensionPolicy
from app.domain.origin import OriginTrigger
from app.domain.runtime import WorkerStatus
from app.infra.log.app import app_log
from app.services.activity.recorder import ActivityRecorder
from app.services.organize.execute import OrganizeExecutor
from app.services.watch.buffer import WatchDispatch, WatchEventBuffer
from app.services.watch.organize import WatchOrganizeRun, WatchRunResult

DEFAULT_WATCH_POLL_INTERVAL_SECONDS = 15.0
DEFAULT_WATCH_STABILITY_DEBOUNCE_SECONDS = 30.0


@dataclass(frozen=True)
class WatchChildRead:
    name: str
    path: Path
    status: str
    origin_id: str | None = None
    media_type: str | None = None
    candidate_count: int = 0
    unknown_count: int = 0


class WatchService:
    def __init__(
        self,
        *,
        configuration,
        matcher,
        organizer: OrganizeExecutor,
        activity: ActivityRecorder,
        extensions: MediaExtensionPolicy,
        min_non_subtitle_file_size_bytes: int | None = None,
        inventory=None,
        poll_interval_seconds: float = DEFAULT_WATCH_POLL_INTERVAL_SECONDS,
        debounce_seconds: float = DEFAULT_WATCH_STABILITY_DEBOUNCE_SECONDS,
    ):
        self.configuration = configuration
        self.matcher = matcher
        self.organizer = organizer
        self.activity = activity
        self.inventory = inventory
        self.extensions = extensions
        self.min_non_subtitle_file_size_bytes = min_non_subtitle_file_size_bytes
        self.poll_interval_seconds = poll_interval_seconds
        self.debounce_seconds = debounce_seconds
        self._worker: WatchEventBuffer | None = None
        self._organize = WatchOrganizeRun(
            matcher=matcher,
            organizer=organizer,
            activity=activity,
            extensions=extensions,
            min_non_subtitle_file_size_bytes=min_non_subtitle_file_size_bytes,
            depot_resolver=self._depot_for_id,
            organize_rule_resolver=self._organize_rule,
        )
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._started_at: datetime | None = None
        self._updated_at: datetime | None = None
        self._last_error: str | None = None
        self._last_event: str | None = None

    @property
    def worker(self) -> WatchEventBuffer | None:
        return self._worker

    def settings(self):
        return self.configuration.get_watch_settings()

    def save_settings(self, config):
        saved = self.configuration.save_watch_settings(config)
        self.update_watch_settings(saved)
        return saved

    def children(self) -> list[WatchChildRead]:
        config = self.configuration.get_watch_settings()
        if config is None:
            return []
        watched_folder_origins = [
            origin for origin in self.configuration.list_origins()
            if origin.trigger == OriginTrigger.WATCH
        ]
        by_name = {origin.path.name.casefold(): origin for origin in watched_folder_origins}
        child_paths: dict[str, Path] = {}
        names = set(by_name)
        if config.path.exists() and config.path.is_dir():
            child_paths = {child.name.casefold(): child for child in config.path.iterdir() if child.is_dir()}
            names.update(child_paths)
        rows: list[WatchChildRead] = []
        for key in sorted(names):
            origin = by_name.get(key)
            path = origin.path if origin else child_paths[key]
            exists = path.exists()
            if origin is None:
                status = "unconfigured"
            elif not exists:
                status = "missing"
            elif not origin.enabled:
                status = "disabled"
            else:
                status = "configured"
            scan = self.inventory.origin_summary(origin) if self.inventory is not None and origin and exists else None
            rows.append(
                WatchChildRead(
                    name=path.name,
                    path=path,
                    status=status,
                    origin_id=origin.id if origin else None,
                    media_type=origin.media_type.value if origin else None,
                    candidate_count=scan.candidate_count if scan else 0,
                    unknown_count=scan.unknown_count if scan else 0,
                )
            )
        return rows

    def start(self) -> None:
        with self._lock:
            self._configure_worker()
            if self._worker:
                self._worker.start()
            self._ensure_thread_locked()
            self._started_at = self._started_at or now()
            self._updated_at = now()

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5)
        with self._lock:
            if self._worker:
                self._worker.stop()
            self._worker = None
            self._thread = None
            self._updated_at = now()

    def status(self) -> WorkerStatus:
        running = bool(self._thread and self._thread.is_alive())
        if self._last_error:
            state = "error"
        elif running:
            state = "running"
        else:
            state = "stopped"
        return WorkerStatus(
            id="watch",
            label="Watch",
            running=running,
            state=state,
            current_item_id=self._last_event,
            last_error=self._last_error,
            started_at=self._started_at,
            updated_at=self._updated_at,
        )

    def start_watch(self) -> WorkerStatus:
        config = self.configuration.get_watch_settings()
        if config is None:
            raise ConfigurationError("WatchSettings is not configured", code="watch.not_configured")
        self.configuration.save_watch_settings(replace(config, enabled=True))
        self.start()
        return self.status()

    def stop_watch(self) -> WorkerStatus:
        config = self.configuration.get_watch_settings()
        if config is not None:
            self.configuration.save_watch_settings(replace(config, enabled=False))
        self.stop()
        return self.status()

    def restart_watch(self) -> WorkerStatus:
        config = self.configuration.get_watch_settings()
        if config is None:
            raise ConfigurationError("WatchSettings is not configured", code="watch.not_configured")
        if not config.enabled:
            raise ConfigurationError("Watch must be started before it can be restarted", code="watch.restart_requires_running")
        self.stop()
        self.start()
        return self.status()

    def refresh(self) -> None:
        with self._lock:
            self._configure_worker()
            self._ensure_thread_locked()

    def update_extensions(self, extensions: MediaExtensionPolicy) -> None:
        with self._lock:
            self.extensions = extensions
            self._organize.extensions = extensions
            self._configure_worker()
            self._ensure_thread_locked()

    def update_min_non_subtitle_file_size(self, min_non_subtitle_file_size_bytes: int | None) -> None:
        with self._lock:
            self.min_non_subtitle_file_size_bytes = min_non_subtitle_file_size_bytes
            self._organize.min_non_subtitle_file_size_bytes = min_non_subtitle_file_size_bytes
            if self._worker is not None:
                self._worker.min_non_subtitle_file_size_bytes = min_non_subtitle_file_size_bytes

    def update_matcher(self, matcher) -> None:
        with self._lock:
            self.matcher = matcher
            self._organize.matcher = matcher

    def update_runtime_settings(self, *, poll_interval_seconds: float, debounce_seconds: float) -> None:
        with self._lock:
            self.poll_interval_seconds = poll_interval_seconds
            self.debounce_seconds = debounce_seconds
            if self._worker is not None:
                self._worker.debounce_seconds = debounce_seconds

    def update_watch_settings(self, watch_settings) -> None:
        if not watch_settings.enabled:
            self.stop()
            return
        with self._lock:
            if self._worker is None:
                self._configure_worker()
                if self._worker:
                    self._worker.start()
            elif normalized_path_key(self._worker.watch_settings.path) != normalized_path_key(watch_settings.path):
                self._configure_worker()
                if self._worker:
                    self._worker.start()
            else:
                self._worker.update_watch_settings(watch_settings)
            self._ensure_thread_locked()

    def update_origin(self, origin) -> None:
        with self._lock:
            if self._worker is None:
                self._configure_worker()
                if self._worker:
                    self._worker.start()
            else:
                self._worker.update_origin(origin)
            self._ensure_thread_locked()

    def poll_once(self) -> WatchRunResult:
        current = None
        with self._lock:
            if self._worker is None:
                self._configure_worker()
            if self._worker:
                self._worker.enqueue_dispatches(self._worker.manual_poll_backlog(), now=current)
                dispatches = self._worker.flush_ready(now=current)
            else:
                dispatches = []
        return self._process(dispatches)

    def process_ready_once(self, *, now: float | None = None) -> WatchRunResult:
        with self._lock:
            if self._worker is None:
                self._configure_worker()
            dispatches = self._worker.flush_ready(now=now) if self._worker else []
        return self._process(dispatches)

    def _configure_worker(self) -> None:
        watch_settings = self.configuration.get_watch_settings()
        if watch_settings is None:
            self._worker = None
            return
        self._worker = WatchEventBuffer(
            watch_settings=watch_settings,
            origins=self.configuration.list_origins(),
            extensions=self.extensions,
            min_non_subtitle_file_size_bytes=self.min_non_subtitle_file_size_bytes,
            debounce_seconds=self.debounce_seconds,
            force_polling=True,
        )

    def _ensure_thread_locked(self) -> None:
        if self._worker is None or not self._worker.watch_settings.enabled:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_watch_loop, name="omedia-watch-stream", daemon=True)
        self._thread.start()

    def _run_watch_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                watched_worker = self._worker
                if watched_worker is None or not watched_worker.watch_settings.enabled:
                    return
                watch_path = watched_worker.watch_settings.path
                force_polling = watched_worker.force_polling
                timeout_ms = max(100, min(1000, int(watched_worker.debounce_seconds * 1000 / 2) or 100))
                poll_delay_ms = max(1, int(self.poll_interval_seconds * 1000))
            try:
                for changes in watch(
                    watch_path,
                    debounce=50,
                    force_polling=force_polling,
                    poll_delay_ms=poll_delay_ms,
                    recursive=True,
                    rust_timeout=timeout_ms,
                    yield_on_timeout=True,
                    stop_event=self._stop_event,
                ):
                    if self._stop_event.is_set():
                        return
                    with self._lock:
                        current_worker = self._worker
                        if current_worker is not watched_worker:
                            break
                        for change, raw_path in changes:
                            self._last_event = str(raw_path)
                            self._updated_at = now()
                            app_log.info("watch.event", "File event received", path=raw_path, event=change)
                            current_worker.handle_event(Path(raw_path), event_type=change)
                        dispatches = current_worker.flush_ready()
                    self._process(dispatches)
            except Exception as exc:
                self._log_watch_failure(exc)
                if self._stop_event.wait(self.poll_interval_seconds):
                    return

    def _log_watch_failure(self, exc: Exception) -> None:
        self._last_error = str(exc)
        self._updated_at = now()
        source = self._worker.watch_settings.path if self._worker else None
        app_log.exception("watch.worker", "Watch worker failed", exc=exc, source_path=source)

    def _process(self, dispatches: list[WatchDispatch]) -> WatchRunResult:
        if not dispatches:
            return WatchRunResult()
        self._last_event = str(dispatches[-1].path)
        self._last_error = None
        self._updated_at = now()
        with self._lock:
            worker = self._worker
            if worker is not None:
                worker.begin_processing()
        try:
            return self._organize.process_dispatches(dispatches)
        finally:
            with self._lock:
                if worker is not None:
                    worker.finish_processing()

    def _depot_for_id(self, depot_id: str):
        return self.configuration.get_depot(depot_id)

    def _organize_rule(self, rule_id: str):
        return self.configuration.store.get_organize_rule(rule_id)


def now() -> datetime:
    return datetime.now().astimezone()
