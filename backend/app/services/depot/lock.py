from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from app.core.path import normalized_path_key
from app.domain.depot import Depot


class DepotLockUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class DepotLockKey:
    value: str


@dataclass
class DepotLockLease:
    key: DepotLockKey
    lock: Lock
    acquired: bool

    def __bool__(self) -> bool:
        return self.acquired

    def __enter__(self) -> "DepotLockLease":
        if not self.acquired:
            raise DepotLockUnavailable(f"Depot lock is unavailable: {self.key.value}")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()

    def release(self) -> None:
        if self.acquired:
            self.lock.release()
            self.acquired = False


class DepotLockRegistry:
    def __init__(self) -> None:
        self._guard = Lock()
        self._locks: dict[str, Lock] = {}

    def key_for(
        self,
        depot: Depot | None = None,
        *,
        depot_id: str | None = None,
        depot_path: Path | str | None = None,
    ) -> DepotLockKey:
        if depot is not None:
            depot_id = depot_id or depot.id
            depot_path = depot_path or depot.path
        if depot_id:
            return DepotLockKey(f"id:{depot_id}")
        if depot_path:
            return DepotLockKey(f"path:{normalized_path_key(Path(depot_path))}")
        raise ValueError("Depot lock requires a Depot, depot_id, or depot_path")

    def acquire(
        self,
        depot: Depot | None = None,
        *,
        depot_id: str | None = None,
        depot_path: Path | str | None = None,
        blocking: bool = True,
        timeout: float | None = None,
    ) -> DepotLockLease:
        key = self.key_for(depot, depot_id=depot_id, depot_path=depot_path)
        lock = self._lock_for(key)
        if timeout is None:
            acquired = lock.acquire(blocking=blocking)
        else:
            acquired = lock.acquire(blocking=blocking, timeout=timeout)
        return DepotLockLease(key=key, lock=lock, acquired=acquired)

    def _lock_for(self, key: DepotLockKey) -> Lock:
        with self._guard:
            lock = self._locks.get(key.value)
            if lock is None:
                lock = Lock()
                self._locks[key.value] = lock
            return lock

