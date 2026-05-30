from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from app.core.error import ConfigurationError
from app.domain.media import MediaExtensionPolicy

DEFAULT_TMDB_BASE_URL = "https://api.themoviedb.org/3"
DEFAULT_TMDB_RATE_LIMIT = 10.0
DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1/"
DEFAULT_LLM_RATE_LIMIT = 1.0
DEFAULT_WATCH_POLL_INTERVAL_SECONDS = 15.0
DEFAULT_WATCH_STABILITY_DEBOUNCE_SECONDS = 30.0
DEFAULT_MIN_NON_SUBTITLE_FILE_SIZE_MB = 50
MIB = 1024 * 1024
TMDB_PROVIDER_REQUIRED_MESSAGE = "TMDB provider settings are required before identifying media"
LLM_PROVIDER_REQUIRED_MESSAGE = "LLM provider settings are required before identifying media"
PROVIDERS_REQUIRED_MESSAGE = "TMDB and LLM provider settings are required before identifying media"


@dataclass(frozen=True)
class ProviderSettings:
    llm_api_key: str | None = None
    tmdb_api_key: str | None = None
    tmdb_base_url: str = DEFAULT_TMDB_BASE_URL
    tmdb_rate_limit: float = DEFAULT_TMDB_RATE_LIMIT
    tmdb_proxy: str | None = None
    llm_base_url: str | None = DEFAULT_LLM_BASE_URL
    llm_model: str | None = None
    llm_batch_size: int = 50
    llm_rate_limit: float = DEFAULT_LLM_RATE_LIMIT
    llm_proxy: str | None = None

    def require_tmdb_key(self) -> str:
        if not self.tmdb_api_key:
            raise ConfigurationError(TMDB_PROVIDER_REQUIRED_MESSAGE, code="provider.tmdb_required", details={"provider": "tmdb"})
        return self.tmdb_api_key

    def require_llm_key(self) -> str:
        if not self.llm_api_key:
            raise ConfigurationError(LLM_PROVIDER_REQUIRED_MESSAGE, code="provider.llm_required", details={"provider": "llm"})
        return self.llm_api_key

    def require_identify(self) -> None:
        missing_tmdb = not self.tmdb_api_key
        missing_llm = not self.llm_api_key
        if missing_tmdb and missing_llm:
            raise ConfigurationError(PROVIDERS_REQUIRED_MESSAGE, code="provider.identify_required", details={"providers": ["tmdb", "llm"]})
        if missing_tmdb:
            raise ConfigurationError(TMDB_PROVIDER_REQUIRED_MESSAGE, code="provider.tmdb_required", details={"provider": "tmdb"})
        if missing_llm:
            raise ConfigurationError(LLM_PROVIDER_REQUIRED_MESSAGE, code="provider.llm_required", details={"provider": "llm"})


@dataclass(frozen=True)
class WatchRuntimeSettings:
    poll_interval_seconds: float = DEFAULT_WATCH_POLL_INTERVAL_SECONDS
    stability_debounce_seconds: float = DEFAULT_WATCH_STABILITY_DEBOUNCE_SECONDS


@dataclass(frozen=True)
class OrganizeSettings:
    extensions: MediaExtensionPolicy
    min_non_subtitle_file_size_bytes: int | None = DEFAULT_MIN_NON_SUBTITLE_FILE_SIZE_MB * MIB

    @property
    def min_non_subtitle_file_size_mb(self) -> int | None:
        if self.min_non_subtitle_file_size_bytes is None:
            return None
        return self.min_non_subtitle_file_size_bytes // MIB


@dataclass
class StartupSettings:
    organize: OrganizeSettings
    providers: ProviderSettings = field(default_factory=ProviderSettings)
    watch: WatchRuntimeSettings = field(default_factory=WatchRuntimeSettings)


def parse_provider_settings(data: Mapping[str, Any]) -> ProviderSettings:
    tmdb = _mapping_or_empty(data.get("tmdb"), "tmdb")
    llm = _mapping_or_empty(data.get("llm"), "llm")
    return ProviderSettings(
        tmdb_api_key=_optional_str(tmdb.get("api_key")),
        tmdb_base_url=_optional_str(tmdb.get("base_url")) or DEFAULT_TMDB_BASE_URL,
        tmdb_rate_limit=_positive_float(tmdb.get("rate_limit", DEFAULT_TMDB_RATE_LIMIT), "tmdb.rate_limit"),
        tmdb_proxy=_optional_proxy_url(tmdb.get("proxy"), "tmdb.proxy"),
        llm_api_key=_optional_str(llm.get("api_key")),
        llm_base_url=_optional_str(llm.get("base_url")) or DEFAULT_LLM_BASE_URL,
        llm_model=_optional_str(llm.get("model")),
        llm_batch_size=_positive_int(llm.get("batch_size", 50), "llm.batch_size"),
        llm_rate_limit=_positive_float(llm.get("rate_limit", DEFAULT_LLM_RATE_LIMIT), "llm.rate_limit"),
        llm_proxy=_optional_proxy_url(llm.get("proxy"), "llm.proxy"),
    )


def parse_watch_settings(data: Mapping[str, Any]) -> WatchRuntimeSettings:
    watch = _mapping_or_empty(data.get("watch"), "watch")
    return WatchRuntimeSettings(
        poll_interval_seconds=_positive_float(
            watch.get("poll_interval_seconds", DEFAULT_WATCH_POLL_INTERVAL_SECONDS),
            "watch.poll_interval_seconds",
        ),
        stability_debounce_seconds=_positive_float(
            watch.get("stability_debounce_seconds", DEFAULT_WATCH_STABILITY_DEBOUNCE_SECONDS),
            "watch.stability_debounce_seconds",
        ),
    )


def parse_organize_settings(data: Mapping[str, Any]) -> OrganizeSettings:
    raw_organize = data.get("organize")
    if raw_organize is None:
        raise ConfigurationError("Common configuration must define organize")
    if not isinstance(raw_organize, Mapping):
        raise ConfigurationError("organize configuration must be an object")
    organize = raw_organize
    raw_extensions = organize.get("extensions")
    if raw_extensions is None:
        raise ConfigurationError("organize.extensions must be defined")
    if not isinstance(raw_extensions, Mapping):
        raise ConfigurationError("organize.extensions must be an object")
    size_mb = _optional_non_negative_int(
        organize.get("min_non_subtitle_file_size_mb", DEFAULT_MIN_NON_SUBTITLE_FILE_SIZE_MB),
        "organize.min_non_subtitle_file_size_mb",
    )
    return OrganizeSettings(
        extensions=MediaExtensionPolicy(
            video=_extension_set(raw_extensions, "video"),
            subtitle=_extension_set(raw_extensions, "subtitle"),
            sidecar=_extension_set(raw_extensions, "sidecar"),
        ),
        min_non_subtitle_file_size_bytes=None if not size_mb else size_mb * MIB,
    )


def _mapping_or_empty(value: Any, label: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"{label} configuration must be an object")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _positive_int(value: Any, label: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{label} must be a positive integer") from exc
    if parsed <= 0:
        raise ConfigurationError(f"{label} must be a positive integer")
    return parsed


def _positive_float(value: Any, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{label} must be a positive number") from exc
    if parsed <= 0:
        raise ConfigurationError(f"{label} must be a positive number")
    return parsed


def _optional_non_negative_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ConfigurationError(f"{label} must be a non-negative integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
    else:
        raise ConfigurationError(f"{label} must be a non-negative integer")
    if parsed < 0:
        raise ConfigurationError(f"{label} must be a non-negative integer")
    return parsed


def _optional_proxy_url(value: Any, label: str) -> str | None:
    text = _optional_str(value)
    if text is None:
        return None
    parsed = urlparse(text)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ConfigurationError(f"{label} must be a plain HTTP proxy URL like http://host:port") from exc
    if (
        parsed.scheme != "http"
        or not parsed.hostname
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ConfigurationError(f"{label} must be a plain HTTP proxy URL like http://host:port")
    return text


def _extension_set(raw: Mapping[str, Any], key: str) -> frozenset[str]:
    if key not in raw:
        raise ConfigurationError(f"organize.extensions.{key} must be defined")
    value = raw.get(key)
    if value is None:
        return frozenset()
    if isinstance(value, str):
        values: Sequence[Any] = [value]
    elif isinstance(value, Sequence):
        values = value
    else:
        raise ConfigurationError(f"organize.extensions.{key} must be a list of extensions")

    normalized = []
    for item in values:
        text = str(item).strip().lower()
        if not text:
            continue
        normalized.append(text if text.startswith(".") else f".{text}")
    return frozenset(normalized)
