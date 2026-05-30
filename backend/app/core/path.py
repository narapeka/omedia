from __future__ import annotations

from functools import lru_cache
import re
from pathlib import Path

from pypinyin import lazy_pinyin

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WHITESPACE = re.compile(r"\s+")
NATURAL_SORT_PART = re.compile(r"\d+|\D+")
DISPLAY_SORT_PINYIN_PREFIX_LENGTH = 32
DISPLAY_SORT_CACHE_SIZE = 8192


def sanitize_filename_component(value: str, replacement: str = " ") -> str:
    cleaned = INVALID_FILENAME_CHARS.sub(replacement, value)
    cleaned = WHITESPACE.sub(" ", cleaned).strip(" .")
    if not cleaned:
        cleaned = "Untitled"
    if cleaned.upper() in WINDOWS_RESERVED_NAMES:
        cleaned = f"{cleaned}_"
    return cleaned


def render_tag_suffix(raw_tag: str) -> str:
    return f"[{sanitize_filename_component(raw_tag)}]"


def normalized_path_key(path: Path) -> str:
    try:
        normalized = path.expanduser().resolve(strict=False)
    except OSError:
        normalized = path.expanduser().absolute()
    return str(normalized).replace("\\", "/").rstrip("/").casefold()


def display_sort_key(value: Path | str) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    text = _sort_text(value)
    return _cached_display_sort_key(text)


def natural_sort_key(value: Path | str) -> tuple[str, ...]:
    return _natural_sort_key(_sort_text(value).casefold())


def safe_relative_to(path: Path, root: Path) -> Path | None:
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return None


@lru_cache(maxsize=DISPLAY_SORT_CACHE_SIZE)
def _cached_display_sort_key(text: str) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    prefix = text[:DISPLAY_SORT_PINYIN_PREFIX_LENGTH]
    pinyin_prefix = "".join(lazy_pinyin(prefix)).casefold()
    return (_natural_sort_key(pinyin_prefix), _natural_sort_key(text.casefold()), text)


def _natural_sort_key(text: str) -> tuple[str, ...]:
    return tuple(_natural_sort_part(part) for part in NATURAL_SORT_PART.findall(text))


def _natural_sort_part(part: str) -> str:
    if part.isdigit():
        return f"{int(part):020d}"
    return part


def _sort_text(value: Path | str) -> str:
    if isinstance(value, Path):
        return value.as_posix()
    return str(value or "")
