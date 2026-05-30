from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from threading import RLock
from typing import Any

DEFAULT_TMDB_CACHE_TTL_SECONDS = 24 * 60 * 60
DEFAULT_TMDB_CACHE_MAX_ENTRIES = 2048
MISSING = object()


@dataclass(frozen=True)
class TMDBCacheStats:
    hits: int
    misses: int
    entries: int


class TTLCache:
    """Small thread-safe TTL/LRU cache for provider responses."""

    def __init__(
        self,
        *,
        ttl_seconds: float = DEFAULT_TMDB_CACHE_TTL_SECONDS,
        max_entries: int = DEFAULT_TMDB_CACHE_MAX_ENTRIES,
        now: Callable[[], float] | None = None,
    ):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        if max_entries <= 0:
            raise ValueError("max_entries must be greater than zero")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._now = now or time.monotonic
        self._items: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = RLock()
        self._hits = 0
        self._misses = 0

    def get_or_set(self, key: Hashable, factory: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not MISSING:
            return cached
        value = factory()
        self.set(key, value)
        return value

    def get(self, key: Hashable) -> Any:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                self._misses += 1
                return MISSING
            expires_at, value = item
            if expires_at <= self._now():
                self._items.pop(key, None)
                self._misses += 1
                return MISSING
            self._items.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._items[key] = (self._now() + self.ttl_seconds, value)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def stats(self) -> TMDBCacheStats:
        with self._lock:
            return TMDBCacheStats(self._hits, self._misses, len(self._items))
