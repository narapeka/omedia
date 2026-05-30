from __future__ import annotations

from typing import Any, Sequence

from app.domain.match import TMDBCandidate, TMDBSearchResult
from app.domain.media import MediaType
from app.infra.tmdb.title import (
    preferred_display_title,
    titles_to_metadata,
    unique_titles,
)


def tmdb_namespace(media_type: MediaType) -> str:
    return "tv" if media_type == MediaType.TV else "movie"


def search_params(
    media_type: MediaType,
    title: str,
    year: int | None,
    language: str,
    page: int,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "query": title,
        "language": language,
        "include_adult": "false",
        "page": str(page),
    }
    if not year:
        return base
    if media_type == MediaType.TV:
        base["first_air_date_year"] = str(year)
        base["year"] = str(year)
    else:
        base["primary_release_year"] = str(year)
        base["year"] = str(year)
    return base


def candidate_from_detail(media_type: MediaType, payload: dict[str, Any]) -> TMDBCandidate:
    if media_type == MediaType.TV:
        title = payload.get("name")
        original_title = payload.get("original_name")
        year = year_from_date(payload.get("first_air_date"))
        genre_ids = genre_ids_from_payload(payload)
        origin_country = payload.get("origin_country") or []
    else:
        title = payload.get("title")
        original_title = payload.get("original_title")
        year = year_from_date(payload.get("release_date"))
        genre_ids = genre_ids_from_payload(payload)
        origin_country = [
            item.get("iso_3166_1")
            for item in payload.get("production_countries", [])
            if item.get("iso_3166_1")
        ]

    directors = directors_from_payload(payload, media_type)
    cast = cast_from_payload(payload)
    alternative_titles = alternative_titles_from_payload(payload, media_type)
    translations = translations_from_payload(payload, media_type)
    title, preferred_title_source = preferred_display_title(
        str(title or original_title or ""),
        str(original_title or ""),
        str(payload.get("original_language") or ""),
        alternative_titles,
        translations,
    )
    metadata = {
        "media_type": media_type.value,
        "title": title,
        "original_title": original_title,
        "year": year,
        "release_year": year,
        "tmdb_id": payload.get("id"),
        "overview": payload.get("overview"),
        "poster_path": payload.get("poster_path"),
        "poster_url": poster_url(payload.get("poster_path")),
        "vote_average": optional_float(payload.get("vote_average")),
        "popularity": optional_float(payload.get("popularity")),
        "genre_ids": genre_ids,
        "origin_country": origin_country,
        "directors": directors,
        "cast": cast,
        "original_language": payload.get("original_language"),
        "alternative_titles": titles_to_metadata(alternative_titles),
        "translations": titles_to_metadata(translations),
        "preferred_title_source": preferred_title_source,
        "external_ids": payload.get("external_ids") or {},
        "detail_loaded": True,
    }
    return TMDBCandidate(
        tmdb_id=int(payload.get("id") or 0),
        media_type=media_type,
        title=str(title),
        original_title=original_title,
        year=year,
        alternative_titles=alternative_titles,
        translations=translations,
        metadata=metadata,
    )


def search_result_from_payload(
    media_type: MediaType,
    payload: dict[str, Any],
) -> TMDBSearchResult | None:
    tmdb_id = payload.get("id")
    if not isinstance(tmdb_id, int):
        return None
    if media_type == MediaType.TV:
        title = payload.get("name")
        original_title = payload.get("original_name")
        year = year_from_date(payload.get("first_air_date"))
        origin_country = payload.get("origin_country") or []
    else:
        title = payload.get("title")
        original_title = payload.get("original_title")
        year = year_from_date(payload.get("release_date"))
        origin_country = []
    display_title = str(title or original_title or "").strip()
    if not display_title:
        return None
    metadata = {
        "media_type": media_type.value,
        "title": display_title,
        "original_title": original_title,
        "year": year,
        "release_year": year,
        "tmdb_id": tmdb_id,
        "overview": payload.get("overview"),
        "poster_path": payload.get("poster_path"),
        "poster_url": poster_url(payload.get("poster_path")),
        "vote_average": optional_float(payload.get("vote_average")),
        "popularity": optional_float(payload.get("popularity")),
        "genre_ids": genre_ids_from_payload(payload),
        "origin_country": origin_country,
        "original_language": payload.get("original_language"),
        "detail_loaded": False,
    }
    return TMDBSearchResult(
        tmdb_id=tmdb_id,
        media_type=media_type,
        title=display_title,
        original_title=str(original_title) if original_title else None,
        year=year,
        metadata=metadata,
    )


def optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def poster_url(value: Any) -> str | None:
    if not value:
        return None
    path = str(value)
    if not path.startswith("/"):
        path = f"/{path}"
    return f"https://image.tmdb.org/t/p/w154{path}"


def year_from_date(value: Any) -> int | None:
    if not value:
        return None
    text = str(value)
    return int(text[:4]) if len(text) >= 4 and text[:4].isdigit() else None


def genre_ids_from_payload(payload: dict[str, Any]) -> list[int]:
    if isinstance(payload.get("genre_ids"), list):
        return [int(value) for value in payload["genre_ids"] if isinstance(value, int)]
    return [int(item["id"]) for item in payload.get("genres", []) if item.get("id") is not None]


def directors_from_payload(payload: dict[str, Any], media_type: MediaType) -> list[str]:
    if media_type == MediaType.TV:
        creators = named_people(payload.get("created_by") or [])
        if creators:
            return creators[:4]
    crew = (payload.get("credits") or {}).get("crew") or []
    names = [
        str(item["name"]).strip()
        for item in crew
        if item.get("name") and str(item.get("job") or "").casefold() == "director"
    ]
    return unique_people(names)[:4]


def cast_from_payload(payload: dict[str, Any]) -> list[str]:
    return named_people((payload.get("credits") or {}).get("cast") or [])[:8]


def named_people(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    names = [str(item["name"]).strip() for item in values if isinstance(item, dict) and item.get("name")]
    return unique_people(names)


def unique_people(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def alternative_titles_from_payload(payload: dict[str, Any], media_type: MediaType) -> list[dict[str, str]]:
    alternative_titles = payload.get("alternative_titles") or {}
    values = alternative_titles.get("results") or alternative_titles.get("titles") or []
    title_fields = ("title", "name") if media_type == MediaType.MOVIE else ("title", "name")
    titles: list[dict[str, str]] = []
    for item in values:
        title = first_text_value(item, title_fields)
        country = item.get("iso_3166_1")
        if title and country:
            titles.append({"title": title, "iso_3166_1": str(country)})
    return unique_titles(titles)


def translations_from_payload(payload: dict[str, Any], media_type: MediaType) -> list[dict[str, str]]:
    values = ((payload.get("translations") or {}).get("translations") or [])
    fields = ("title", "name") if media_type == MediaType.MOVIE else ("name", "title")
    titles: list[dict[str, str]] = []
    for item in values:
        title = first_text_value(item.get("data") or {}, fields)
        country = item.get("iso_3166_1")
        if not title or not country:
            continue
        value = {"title": title, "iso_3166_1": str(country)}
        if item.get("iso_639_1"):
            value["iso_639_1"] = str(item["iso_639_1"])
        titles.append(value)
    return unique_titles(titles)


def first_text_value(value: dict[str, Any], fields: Sequence[str]) -> str | None:
    for field in fields:
        item = value.get(field)
        if item:
            return str(item)
    return None


def looks_like_bearer_token(value: str) -> bool:
    normalized = value.strip()
    return normalized.startswith("Bearer ") or normalized.startswith("eyJ")
