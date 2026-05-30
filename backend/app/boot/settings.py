from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.core.error import ConfigurationError
from app.services.config.values import (
    StartupSettings as _StartupSettings,
    parse_organize_settings as _parse_organize_settings,
    parse_provider_settings as _parse_provider_settings,
    parse_watch_settings as _parse_watch_settings,
)


def load_startup_settings(
    *,
    common_path: str | Path,
) -> _StartupSettings:
    common_data = _read_config_object(Path(common_path), "Common")
    return _StartupSettings(
        organize=_parse_organize_settings(common_data),
        providers=_parse_provider_settings(common_data),
        watch=_parse_watch_settings(common_data),
    )


def _read_structured_file(path: Path) -> Any:
    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml
    except ImportError as exc:
        raise ConfigurationError("YAML config requires PyYAML; use JSON or install PyYAML") from exc
    return yaml.safe_load(text) or {}


def _read_config_object(path: Path, label: str) -> Mapping[str, Any]:
    data = _read_structured_file(path)
    if not isinstance(data, Mapping):
        raise ConfigurationError(f"{label} configuration root must be an object: {path}")
    return data


__all__ = ["load_startup_settings"]
