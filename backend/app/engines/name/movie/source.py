from __future__ import annotations

import re
from pathlib import Path

from app.core.path import render_tag_suffix
from app.domain.media import MediaExtensionPolicy
from app.domain.movie import MovieIdentity, MovieTagSuffix


def extract_movie_source_name(
    path: Path,
    extensions: MediaExtensionPolicy,
) -> tuple[str, int | None, MovieTagSuffix | None]:
    media_suffixes = extensions.supported
    source = path.stem if path.suffix.lower() in media_suffixes else path.name
    tag = extract_movie_tag(source)
    if tag:
        source = re.sub(r"#[^#]+#", " ", source)
    year = extract_year(source)
    title = source
    if year:
        title = re.sub(rf"[\s._(-]*{year}[\s._)-]*", " ", title, count=1)
    title = re.sub(r"[._]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title or path.stem, year, tag


def extract_movie_tag(source_name: str) -> MovieTagSuffix | None:
    matches = re.findall(r"#([^#]+)#", source_name)
    if not matches:
        return None
    raw = matches[-1]
    return MovieTagSuffix(raw_tag=raw, rendered_suffix=render_tag_suffix(raw))


def extract_year(value: str) -> int | None:
    match = re.search(r"\b((?:19|20)\d{2})\b", value)
    return int(match.group(1)) if match else None


def build_movie_identity(
    source_path: Path,
    *,
    title: str | None = None,
    year: int | None = None,
    tmdb_id: int | None = None,
    extensions: MediaExtensionPolicy,
) -> MovieIdentity:
    media_suffixes = extensions.supported
    parsed_title, parsed_year, tag = extract_movie_source_name(source_path, extensions=extensions)
    return MovieIdentity(
        source_name=source_path.stem if source_path.suffix.lower() in media_suffixes else source_path.name,
        title=title or parsed_title,
        year=year if year is not None else parsed_year,
        tmdb_id=tmdb_id,
        tag=tag,
    )
