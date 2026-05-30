from __future__ import annotations

import re
import threading
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SECRET_KEY_PATTERN = re.compile(r"(api[_-]?key|authorization|bearer|token|password|secret)", re.IGNORECASE)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"\b(api[_-]?key|authorization|bearer|token|password|secret)\b\s*[:=]\s*([^,\s&;]+)",
    re.IGNORECASE,
)
LOG_RETENTION_DAYS = 30


class AppLog:
    def __init__(self) -> None:
        self._directory: Path | None = None
        self._lock = threading.Lock()

    def configure(self, directory: str | Path) -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self.prune()

    def info(self, category: str, message: str, **context: Any) -> None:
        self._write("INFO", category, message, context)

    def warning(self, category: str, message: str, **context: Any) -> None:
        self._write("WARN", category, message, context)

    def error(self, category: str, message: str, **context: Any) -> None:
        self._write("ERROR", category, message, context)

    def exception(self, category: str, message: str, exc: BaseException | None = None, **context: Any) -> None:
        error = exc or context.pop("exception", None)
        if error is not None:
            context.setdefault("error_type", type(error).__name__)
            context.setdefault("message", str(error))
            context.setdefault("traceback", _limited_traceback(error))
        self._write("ERROR", category, message, context)

    def prune(self) -> None:
        directory = self._directory
        if directory is None or not directory.exists():
            return
        cutoff = datetime.now().date() - timedelta(days=LOG_RETENTION_DAYS)
        for path in directory.glob("omedia-*.log"):
            try:
                stamp = datetime.strptime(path.stem.removeprefix("omedia-"), "%Y-%m-%d").date()
            except ValueError:
                continue
            if stamp < cutoff:
                try:
                    path.unlink()
                except OSError:
                    continue

    def _write(self, level: str, category: str, message: str, context: dict[str, Any]) -> None:
        directory = self._directory
        if directory is None:
            return
        now = datetime.now().astimezone()
        path = directory / f"omedia-{now:%Y-%m-%d}.log"
        lines = [f"{now:%Y-%m-%d %H:%M:%S.%f}"[:-3] + f" {level:<5} [{category}] {message}"]
        for key, value in sorted(context.items()):
            if value is None:
                continue
            lines.append(f"{key}: {_redact(key, value)}")
        block = "\n".join(lines) + "\n\n"
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(block)


app_log = AppLog()


def _redact(key: str, value: Any) -> str:
    if SECRET_KEY_PATTERN.search(key):
        return "[redacted]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{child_key}: {_redact(str(child_key), child_value)}" for child_key, child_value in value.items()) + "}"
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_redact(key, item) for item in value)
    text = str(value)
    if SECRET_KEY_PATTERN.search(text):
        text = _redact_url(text)
        text = re.sub(r"(Bearer\s+)[^\s,]+", r"\1[redacted]", text, flags=re.IGNORECASE)
        text = SECRET_ASSIGNMENT_PATTERN.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    return text


def _redact_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    if not parts.query:
        return value
    query = urlencode(
        [
            (key, "[redacted]" if SECRET_KEY_PATTERN.search(key) else item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
        ]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def _limited_traceback(exc: BaseException) -> str:
    lines = traceback.format_exception(type(exc), exc, exc.__traceback__, limit=8)
    return "".join(lines).strip()
