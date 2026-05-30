from __future__ import annotations

import re
from pathlib import Path

_TOKEN_SEPARATORS = re.compile(r"[\s._\-()[\]{}]+")
_ASCII_PART_TOKEN = re.compile(
    r"^(?:PART[0-9ABI]{0,2}|CD[0-9]{0,2}|DVD[0-9]{0,2}|DISK[0-9]{0,2}|DISC[0-9]{0,2}|D[0-9]{2})$",
    re.IGNORECASE,
)
_VARIANT_TOKENS = {
    "theatrical": "Theatrical",
    "extended": "Extended",
}
_CJK_VARIANT_TOKENS = {"\u5267\u573a\u7248", "\u52a0\u957f\u7248"}


def extract_movie_part_token(path: Path) -> str | None:
    for segment in movie_filename_token_segments(path.stem):
        lowered = segment.casefold()
        if lowered in _VARIANT_TOKENS:
            return _VARIANT_TOKENS[lowered]
        if segment in _CJK_VARIANT_TOKENS:
            return segment
        if _ASCII_PART_TOKEN.match(segment):
            return segment.upper()
    return None


def movie_filename_token_segments(stem: str) -> list[str]:
    return [
        segment
        for segment in _TOKEN_SEPARATORS.split(stem)
        if segment
    ]
