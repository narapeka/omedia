from __future__ import annotations

import gzip
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from threading import Lock, Semaphore
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener, urlopen

from app.infra.log.app import app_log


@dataclass(frozen=True)
class RequesterPolicy:
    retry_statuses: frozenset[int]
    max_retries: int
    backoff_initial_seconds: float
    backoff_max_seconds: float
    max_concurrency: int

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")
        if self.backoff_initial_seconds <= 0:
            raise ValueError("backoff_initial_seconds must be greater than zero")
        if self.backoff_max_seconds <= 0:
            raise ValueError("backoff_max_seconds must be greater than zero")
        if self.max_concurrency <= 0:
            raise ValueError("max_concurrency must be greater than zero")


class ProviderRequester:
    """Shared transport guardrails for external provider HTTP requests."""

    def __init__(
        self,
        *,
        name: str,
        rate_limit: float,
        proxy: str | None = None,
        policy: RequesterPolicy,
        opener: Any | None = None,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
        jitter: Callable[[float], float] | None = None,
    ):
        if rate_limit <= 0:
            raise ValueError("rate_limit must be greater than zero")
        self.name = name
        self.rate_limit = float(rate_limit)
        self.min_interval_seconds = 1.0 / self.rate_limit
        self.proxy = proxy
        self.policy = policy
        self._opener = opener or _opener_for_proxy(proxy)
        self._clock = clock or time.monotonic
        self._sleeper = sleeper or time.sleep
        self._jitter = jitter or _default_jitter
        self._pace_lock = Lock()
        self._last_request_started_at: float | None = None
        self._concurrency = Semaphore(policy.max_concurrency)

    def read(self, request: Request, *, timeout_seconds: float) -> bytes:
        with self._concurrency:
            attempt = 0
            while True:
                self._wait_for_slot()
                try:
                    with self._opener.open(request, timeout=timeout_seconds) as response:
                        app_log.info("provider.request", "Provider request completed", provider=self.name, url=request.full_url)
                        return _decoded_response_body(response)
                except HTTPError as exc:
                    if not self._should_retry(exc, attempt):
                        app_log.error("provider.request", "Provider request failed", provider=self.name, url=request.full_url, status=exc.code)
                        raise
                    app_log.warning("provider.request", "Provider request retry scheduled", provider=self.name, url=request.full_url, status=exc.code, attempt=attempt + 1)
                    self._sleep_before_retry(attempt, exc=exc)
                    attempt += 1
                except (URLError, TimeoutError, OSError) as exc:
                    if not self._should_retry_transport_error(attempt):
                        app_log.error("provider.request", "Provider request failed", provider=self.name, url=request.full_url, error=str(exc))
                        raise
                    app_log.warning("provider.request", "Provider request retry scheduled", provider=self.name, url=request.full_url, error=str(exc), attempt=attempt + 1)
                    self._sleep_before_retry(attempt)
                    attempt += 1

    def _wait_for_slot(self) -> None:
        with self._pace_lock:
            if self._last_request_started_at is not None:
                elapsed = self._clock() - self._last_request_started_at
                if elapsed < self.min_interval_seconds:
                    self._sleeper(self.min_interval_seconds - elapsed)
            self._last_request_started_at = self._clock()

    def _should_retry(self, exc: HTTPError, attempt: int) -> bool:
        return exc.code in self.policy.retry_statuses and attempt < self.policy.max_retries

    def _should_retry_transport_error(self, attempt: int) -> bool:
        return attempt < self.policy.max_retries

    def _sleep_before_retry(self, attempt: int, *, exc: HTTPError | None = None) -> None:
        if exc is not None:
            retry_after = _retry_after_seconds(exc, self._clock)
            if retry_after is not None:
                self._sleeper(retry_after)
                return
        base_delay = min(
            self.policy.backoff_max_seconds,
            self.policy.backoff_initial_seconds * (2 ** attempt),
        )
        self._sleeper(base_delay + self._jitter(base_delay))


class _UrlOpenAdapter:
    def open(self, request: Request, *, timeout: float):
        return urlopen(request, timeout=timeout)


def _opener_for_proxy(proxy: str | None):
    if not proxy:
        return _UrlOpenAdapter()
    return build_opener(ProxyHandler({"http": proxy, "https": proxy}))


def _retry_after_seconds(exc: HTTPError, clock: Callable[[], float]) -> float | None:
    value = exc.headers.get("Retry-After") if exc.headers else None
    if not value:
        return None
    text = value.strip()
    try:
        seconds = float(text)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
        if retry_at.tzinfo is None:
            return None
        seconds = retry_at.timestamp() - time.time()
    return max(0.0, seconds)


def _default_jitter(base_delay: float) -> float:
    return random.uniform(0, min(1.0, base_delay * 0.25))


def _decoded_response_body(response: Any) -> bytes:
    body = response.read()
    content_encoding = _content_encoding(response).lower()
    if "gzip" in content_encoding or body.startswith(b"\x1f\x8b"):
        return gzip.decompress(body)
    return body


def _content_encoding(response: Any) -> str:
    getheader = getattr(response, "getheader", None)
    if callable(getheader):
        return str(getheader("Content-Encoding") or "")
    headers = getattr(response, "headers", None)
    if headers is not None and hasattr(headers, "get"):
        return str(headers.get("Content-Encoding") or "")
    return ""
