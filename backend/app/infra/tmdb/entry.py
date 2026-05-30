from __future__ import annotations

from typing import Any, Sequence

from app.domain.cache import TMDBDetailCache
from app.domain.match import TMDBCandidate
from app.domain.media import MediaType


def candidate_to_cache(candidate: TMDBCandidate) -> dict[str, Any]:
    return {
        "media_type": candidate.media_type.value,
        "tmdb_id": candidate.tmdb_id,
        "title": candidate.title,
        "original_title": candidate.original_title,
        "year": candidate.year,
        "alternative_titles": titles_to_cache(candidate.alternative_titles),
        "translations": titles_to_cache(candidate.translations),
        "metadata": dict(candidate.metadata),
    }


def candidate_from_cache(entry: TMDBDetailCache, media_type: MediaType, tmdb_id: int) -> TMDBCandidate | None:
    value = dict(entry.metadata)
    if value.get("media_type") != media_type.value:
        return None
    try:
        if int(value.get("tmdb_id")) != int(tmdb_id):
            return None
        candidate_media_type = MediaType(value["media_type"])
        candidate_tmdb_id = int(value["tmdb_id"])
        raw_title = value["title"]
        if not raw_title:
            return None
        candidate_title = str(raw_title)
    except (TypeError, ValueError):
        return None
    except KeyError:
        return None
    return TMDBCandidate(
        media_type=candidate_media_type,
        tmdb_id=candidate_tmdb_id,
        title=candidate_title,
        original_title=value.get("original_title"),
        year=value.get("year"),
        alternative_titles=titles_from_cache(value.get("alternative_titles")),
        translations=titles_from_cache(value.get("translations")),
        metadata=dict(value.get("metadata") or {}),
    )


def titles_to_cache(values: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    return [dict(value) for value in values if value.get("title")]


def titles_from_cache(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    titles: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = title_from_cache(item)
        if title:
            titles.append(title)
    return titles


def title_from_cache(value: dict[str, Any]) -> dict[str, str] | None:
    title = value.get("title")
    if not title:
        return None
    result = {"title": str(title)}
    if value.get("iso_3166_1"):
        result["iso_3166_1"] = str(value["iso_3166_1"])
    if value.get("iso_639_1"):
        result["iso_639_1"] = str(value["iso_639_1"])
    return result
