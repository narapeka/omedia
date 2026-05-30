from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.path import normalized_path_key, safe_relative_to
from app.domain.origin import UNKNOWN_FOLDER_NAME, Origin, OriginTrigger
from app.domain.watch import WatchSettings
from app.domain.media import MediaExtensionPolicy
from app.engines.scan.watch import resolve_watch_source_package, scan_watch_source_packages

WATCH_DISPATCH_SOURCE_LIVE = "live"
WATCH_DISPATCH_SOURCE_SERVICE_START_BACKLOG = "service_start_backlog"
WATCH_DISPATCH_SOURCE_WATCH_CONFIG_ENABLED_BACKLOG = "watch_settings_enabled_backlog"
WATCH_DISPATCH_SOURCE_ORIGIN_ENABLED_BACKLOG = "origin_enabled_backlog"
WATCH_DISPATCH_SOURCE_MANUAL_POLL = "manual_poll"


@dataclass(frozen=True)
class WatchSnapshotFile:
    relative_path: str
    size_bytes: int
    modified_time: float


@dataclass(frozen=True)
class WatchCandidateSnapshot:
    files: tuple[WatchSnapshotFile, ...]

    @property
    def count(self) -> int:
        return len(self.files)


@dataclass(frozen=True)
class WatchDispatch:
    origin: Origin
    event_path: Path
    candidate_path: Path
    source: str = WATCH_DISPATCH_SOURCE_LIVE
    event_type: str | None = None
    event_paths: tuple[Path, ...] = field(default_factory=tuple)
    rejected_reason: str | None = None
    first_event_at: float | None = None
    last_event_at: float | None = None
    stability_snapshot: WatchCandidateSnapshot | None = None
    stability_retry_count: int = 0
    trace_id: str = field(default_factory=lambda: f"watch-dispatch-{uuid4()}")

    @property
    def path(self) -> Path:
        return self.event_path

    @property
    def stability_snapshot_count(self) -> int | None:
        return self.stability_snapshot.count if self.stability_snapshot is not None else None


class WatchEventBuffer:
    def __init__(
        self,
        *,
        watch_settings: WatchSettings,
        origins: list[Origin] | None = None,
        extensions: MediaExtensionPolicy | None = None,
        min_non_subtitle_file_size_bytes: int | None = None,
        debounce_seconds: float = 1.0,
        force_polling: bool = True,
    ):
        if origins is None or extensions is None:
            raise ValueError("WatchEventBuffer requires origins and extensions")
        self.watch_settings = watch_settings
        self.origins = origins
        self.extensions = extensions
        self.min_non_subtitle_file_size_bytes = min_non_subtitle_file_size_bytes
        self.debounce_seconds = debounce_seconds
        self.force_polling = force_polling
        self._pending: dict[tuple[str, str], WatchDispatch] = {}
        self._last_event_at: float | None = None
        self._running = False
        self._processing = False

    def start(self, *, now: float | None = None) -> list[WatchDispatch]:
        if self._running:
            return []
        self._running = True
        dispatches = self.service_start_backlog()
        return self.enqueue_dispatches(dispatches, now=now)

    def stop(self) -> None:
        self._running = False
        self._processing = False
        self._pending.clear()
        self._last_event_at = None

    def update_watch_settings(self, watch_settings: WatchSettings) -> list[WatchDispatch]:
        was_enabled = self.watch_settings.enabled
        self.watch_settings = watch_settings
        if not was_enabled and watch_settings.enabled and self._running:
            return self.enqueue_dispatches(self.watch_settings_enabled_backlog())
        return []

    def update_origin(self, origin: Origin) -> list[WatchDispatch]:
        previous = {item.id: item for item in self.origins}.get(origin.id)
        self.origins = [item for item in self.origins if item.id != origin.id]
        self.origins.append(origin)
        if (previous is None or not previous.enabled) and origin.enabled and self.watch_settings.enabled and self._running:
            return self.enqueue_dispatches(self.origin_enabled_backlog(origin))
        return []

    def handle_event(
        self,
        path: Path,
        *,
        now: float | None = None,
        event_type=None,
        source: str = WATCH_DISPATCH_SOURCE_LIVE,
    ) -> WatchDispatch | None:
        dispatch = self.dispatch_for_path(path, event_type=event_type, source=source, now=now)
        if dispatch is None:
            return None
        return self.enqueue_dispatch(dispatch, now=now)

    def enqueue_dispatches(self, dispatches: list[WatchDispatch], *, now: float | None = None) -> list[WatchDispatch]:
        accepted: list[WatchDispatch] = []
        for dispatch in dispatches:
            accepted_dispatch = self.enqueue_dispatch(dispatch, now=now)
            if accepted_dispatch is not None:
                accepted.append(accepted_dispatch)
        return accepted

    def enqueue_dispatch(self, dispatch: WatchDispatch, *, now: float | None = None) -> WatchDispatch | None:
        if not self.watch_settings.enabled:
            return None
        if not dispatch.origin.enabled or dispatch.origin.trigger != OriginTrigger.WATCH:
            return None
        snapshot = candidate_snapshot(dispatch.candidate_path)
        package = resolve_watch_source_package(
            dispatch.origin,
            dispatch.candidate_path,
            self.extensions,
            min_non_subtitle_file_size_bytes=self.min_non_subtitle_file_size_bytes,
        )
        if snapshot is None or package is None:
            return None
        current = now if now is not None else datetime.now(timezone.utc).timestamp()
        key = dispatch_key(dispatch)
        event_paths = append_unique_path(dispatch.event_paths or (dispatch.event_path,), dispatch.event_path)
        prepared = replace(
            dispatch,
            event_paths=event_paths,
            first_event_at=dispatch.first_event_at or current,
            last_event_at=current,
            stability_snapshot=snapshot,
            rejected_reason=package.rejected_reason,
        )
        existing = self._pending.get(key)
        if existing is not None:
            prepared = merge_dispatches(existing, prepared, now=current)
        self._pending[key] = prepared
        self._last_event_at = current
        return prepared

    def flush_ready(self, *, now: float | None = None) -> list[WatchDispatch]:
        if self._processing or self._last_event_at is None:
            return []
        current = now if now is not None else datetime.now(timezone.utc).timestamp()
        if current - self._last_event_at < self.debounce_seconds:
            return []
        ready: list[WatchDispatch] = []
        changed = False
        for key, dispatch in list(self._pending.items()):
            package = resolve_watch_source_package(
                dispatch.origin,
                dispatch.candidate_path,
                self.extensions,
                min_non_subtitle_file_size_bytes=self.min_non_subtitle_file_size_bytes,
            )
            if package is None:
                del self._pending[key]
                continue
            snapshot = candidate_snapshot(dispatch.candidate_path)
            if snapshot is None:
                del self._pending[key]
                continue
            if dispatch.stability_snapshot != snapshot:
                self._pending[key] = replace(
                    dispatch,
                    stability_snapshot=snapshot,
                    stability_retry_count=dispatch.stability_retry_count + 1,
                    last_event_at=current,
                )
                changed = True
                continue
            ready.append(replace(dispatch, stability_snapshot=snapshot, rejected_reason=package.rejected_reason))
            del self._pending[key]
        if self._pending:
            self._last_event_at = current if changed else self._last_event_at
        else:
            self._last_event_at = None
        return ready

    def begin_processing(self) -> None:
        self._processing = True

    def finish_processing(self) -> None:
        self._processing = False

    def dispatch_for_path(
        self,
        path: Path,
        *,
        event_type=None,
        source: str = WATCH_DISPATCH_SOURCE_LIVE,
        now: float | None = None,
    ) -> WatchDispatch | None:
        if not self.watch_settings.enabled:
            return None
        if _is_delete_event_type(event_type):
            return None
        relative = safe_relative_to(path, self.watch_settings.path)
        if relative is None or not relative.parts:
            return None
        child = relative.parts[0]
        origin = self._origin_by_child(child)
        if origin is None or not origin.enabled or origin.trigger != OriginTrigger.WATCH:
            return None
        origin_relative = safe_relative_to(path, origin.path)
        if origin_relative is not None and any(part.casefold() == UNKNOWN_FOLDER_NAME for part in origin_relative.parts):
            return None
        package = resolve_watch_source_package(
            origin,
            path,
            self.extensions,
            min_non_subtitle_file_size_bytes=self.min_non_subtitle_file_size_bytes,
        )
        if package is None:
            return None
        current = now if now is not None else datetime.now(timezone.utc).timestamp()
        return WatchDispatch(
            origin=origin,
            event_path=path,
            candidate_path=package.path,
            source=source,
            event_type=_event_type_text(event_type),
            event_paths=(path,),
            rejected_reason=package.rejected_reason,
            first_event_at=current,
            last_event_at=current,
        )

    def service_start_backlog(self) -> list[WatchDispatch]:
        if not self.watch_settings.enabled:
            return []
        return self._backlog_for_origins(
            [origin for origin in self.origins if origin.enabled],
            source=WATCH_DISPATCH_SOURCE_SERVICE_START_BACKLOG,
        )

    def watch_settings_enabled_backlog(self) -> list[WatchDispatch]:
        if not self.watch_settings.enabled:
            return []
        return self._backlog_for_origins(
            [origin for origin in self.origins if origin.enabled],
            source=WATCH_DISPATCH_SOURCE_WATCH_CONFIG_ENABLED_BACKLOG,
        )

    def origin_enabled_backlog(self, origin: Origin) -> list[WatchDispatch]:
        if not self.watch_settings.enabled or not origin.enabled:
            return []
        return self._backlog_for_origins([origin], source=WATCH_DISPATCH_SOURCE_ORIGIN_ENABLED_BACKLOG)

    def manual_poll_backlog(self) -> list[WatchDispatch]:
        if not self.watch_settings.enabled:
            return []
        return self._backlog_for_origins(
            [origin for origin in self.origins if origin.enabled],
            source=WATCH_DISPATCH_SOURCE_MANUAL_POLL,
        )

    def _backlog_for_origins(self, origins: list[Origin], *, source: str) -> list[WatchDispatch]:
        dispatches: list[WatchDispatch] = []
        for origin in origins:
            if not origin.enabled or origin.trigger != OriginTrigger.WATCH:
                continue
            for package in scan_watch_source_packages(
                origin,
                self.extensions,
                min_non_subtitle_file_size_bytes=self.min_non_subtitle_file_size_bytes,
            ):
                dispatches.append(
                    WatchDispatch(
                        origin=origin,
                        event_path=package.path,
                        candidate_path=package.path,
                        source=source,
                        event_type="added",
                        event_paths=(package.path,),
                        rejected_reason=package.rejected_reason,
                    )
                )
        return dispatches

    def _origin_by_child(self, child: str) -> Origin | None:
        for origin in self.origins:
            if normalized_path_key(origin.path.parent) != normalized_path_key(self.watch_settings.path):
                continue
            if origin.path.name.casefold() == child.casefold():
                return origin
        return None

def _event_type_text(event_type) -> str | None:
    if event_type is None:
        return None
    name = getattr(event_type, "name", None)
    if name:
        return str(name).lower()
    return str(event_type).lower()


def _is_delete_event_type(event_type) -> bool:
    return _event_type_text(event_type) in {"deleted", "delete", "removed", "remove", "3"}


def candidate_snapshot(path: Path) -> WatchCandidateSnapshot | None:
    if not path.exists():
        return None
    files: list[WatchSnapshotFile] = []
    if path.is_file() and not path.is_symlink():
        try:
            stat = path.stat()
        except OSError:
            return None
        files.append(
            WatchSnapshotFile(
                relative_path=path.name,
                size_bytes=stat.st_size,
                modified_time=stat.st_mtime_ns,
            )
        )
        return WatchCandidateSnapshot(tuple(files))
    if not path.is_dir():
        return None
    for child in path.rglob("*"):
        try:
            relative = child.relative_to(path)
        except ValueError:
            continue
        if any(part.casefold() == UNKNOWN_FOLDER_NAME for part in relative.parts):
            continue
        if child.is_symlink() or not child.is_file():
            continue
        try:
            stat = child.stat()
        except OSError:
            return None
        files.append(
            WatchSnapshotFile(
                relative_path=relative.as_posix(),
                size_bytes=stat.st_size,
                modified_time=stat.st_mtime_ns,
            )
        )
    return WatchCandidateSnapshot(tuple(sorted(files, key=lambda item: item.relative_path.casefold())))


def dispatch_key(dispatch: WatchDispatch) -> tuple[str, str]:
    return (dispatch.origin.id, normalized_path_key(dispatch.candidate_path))


def append_unique_path(paths: tuple[Path, ...], path: Path) -> tuple[Path, ...]:
    items = list(paths)
    key = normalized_path_key(path)
    if all(normalized_path_key(item) != key for item in items):
        items.append(path)
    return tuple(items)


def merge_dispatches(existing: WatchDispatch, incoming: WatchDispatch, *, now: float) -> WatchDispatch:
    event_paths = existing.event_paths
    for path in incoming.event_paths or (incoming.event_path,):
        event_paths = append_unique_path(event_paths, path)
    return replace(
        existing,
        event_path=incoming.event_path,
        source=incoming.source,
        event_type=incoming.event_type or existing.event_type,
        event_paths=event_paths,
        rejected_reason=incoming.rejected_reason,
        first_event_at=existing.first_event_at or incoming.first_event_at,
        last_event_at=now,
        stability_snapshot=incoming.stability_snapshot,
        stability_retry_count=existing.stability_retry_count,
    )

