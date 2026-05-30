from __future__ import annotations

import re
from collections.abc import Iterable

from app.domain.media import MediaType
from app.domain.match import (
    MatchContext,
    TVSourceContext,
    TVYearFact,
    TVYearFactSource,
    TVYearScope,
)
from app.domain.media import MediaCandidate, MediaExtensionPolicy, MediaFile
from app.domain.tv import TV_STRUCTURE_MIXED
from app.engines.name.tv.pattern import has_positive_season, has_positive_season_zero
from app.engines.name.tv.source import extract_season_number, valid_season

_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
_TMDB_ID = re.compile(r"\{?\btmdb[-_ ]?\d+\}?", re.IGNORECASE)
_TAG = re.compile(r"#[^#]+#")
_ASCII_SEASON = re.compile(
    r"[Ss](?:eason[.\s_-]*)?\d+(?=[EePp]|\b|[.\s_-])",
    re.IGNORECASE,
)
_CHINESE_SEASON = re.compile(
    r"(?:\u7b2c)?[\u96f6\u3007\u4e00\u4e24\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u4f70\u5343\u4edf\d]+\u5b63",
    re.IGNORECASE,
)


def derive_match_context(candidate: MediaCandidate, extensions: MediaExtensionPolicy) -> MatchContext:
    if candidate.media_type != MediaType.TV:
        return MatchContext(media_type=candidate.media_type)
    return MatchContext(
        media_type=candidate.media_type,
        tv=derive_tv_source_context(candidate, extensions),
    )


def derive_tv_source_context(candidate: MediaCandidate, extensions: MediaExtensionPolicy) -> TVSourceContext:
    files = _organizable_files(candidate.files, extensions)
    direct_files = _direct_files(files)
    subfolder_files = _subfolder_files(files)
    parent_name = candidate.candidate_path.name or candidate.display_name
    parent_year = _first_year(parent_name)
    direct_season = _direct_segment_season(parent_name, direct_files)
    year_facts: list[TVYearFact] = []
    detected_seasons: list[int] = []

    if direct_season is not None:
        detected_seasons.append(direct_season)

    if parent_year is not None:
        if direct_files and direct_season is not None and direct_season != 1:
            year_facts.append(
                TVYearFact(
                    year=parent_year,
                    scope=TVYearScope.SHOW_OR_SEASON_YEAR,
                    season=direct_season,
                    source=(
                        TVYearFactSource.DIRECT_ROOT_SEGMENT
                        if candidate.structure == TV_STRUCTURE_MIXED
                        else TVYearFactSource.CANDIDATE_FOLDER
                    ),
                    label=parent_name,
                )
            )
        else:
            year_facts.append(
                TVYearFact(
                    year=parent_year,
                    scope=TVYearScope.SHOW_YEAR,
                    source=TVYearFactSource.CANDIDATE_FOLDER,
                    label=parent_name,
                )
            )

    for folder_name in _subfolder_names(subfolder_files):
        season = _explicit_season_from_text(folder_name, mode="folder")
        year = _first_year(folder_name)
        if season is not None:
            detected_seasons.append(season)
        if season is None or year is None:
            continue
        year_facts.append(
            TVYearFact(
                year=year,
                scope=TVYearScope.SEASON_YEAR,
                season=season,
                source=TVYearFactSource.SEASON_SUBFOLDER,
                label=folder_name,
            )
        )

    return TVSourceContext(
        structure=candidate.structure,
        show_title_source=_show_title_source(
            parent_name,
            years=[fact.year for fact in year_facts if fact.source != TVYearFactSource.SEASON_SUBFOLDER],
            remove_season=direct_season is not None,
        ),
        year_facts=tuple(year_facts),
        detected_seasons=_unique_ints(detected_seasons),
    )


def _organizable_files(files: Iterable[MediaFile], extensions: MediaExtensionPolicy) -> list[MediaFile]:
    allowed = extensions.video | extensions.subtitle
    return sorted(
        [file for file in files if file.extension.lower() in allowed],
        key=lambda item: item.relative_path.as_posix().lower(),
    )


def _direct_files(files: Iterable[MediaFile]) -> list[MediaFile]:
    return [file for file in files if len(file.relative_path.parts) == 1]


def _subfolder_files(files: Iterable[MediaFile]) -> list[MediaFile]:
    return [file for file in files if len(file.relative_path.parts) > 1]


def _subfolder_names(files: Iterable[MediaFile]) -> tuple[str, ...]:
    names = {
        file.relative_path.parts[0]
        for file in files
        if len(file.relative_path.parts) > 1
    }
    return tuple(sorted(names, key=str.casefold))


def _direct_segment_season(parent_name: str, direct_files: list[MediaFile]) -> int | None:
    parent_season = _explicit_season_from_text(parent_name, mode="folder")
    if parent_season is not None:
        return parent_season
    for file in direct_files:
        season = _explicit_season_from_text(file.path.name, mode="file")
        if season is not None:
            return season
    return None


def _explicit_season_from_text(text: str, *, mode: str) -> int | None:
    if not has_positive_season(text) and not has_positive_season_zero(text):
        return None
    return valid_season(extract_season_number(text, fallback=None, mode=mode))


def _first_year(text: str) -> int | None:
    match = _YEAR.search(text)
    return int(match.group(1)) if match else None


def _show_title_source(parent_name: str, *, years: Iterable[int], remove_season: bool) -> str:
    cleaned = _TAG.sub(" ", parent_name)
    cleaned = _TMDB_ID.sub(" ", cleaned)
    for year in years:
        cleaned = re.sub(rf"\b{int(year)}\b", " ", cleaned, count=1)
    if remove_season:
        cleaned = _ASCII_SEASON.sub(" ", cleaned, count=1)
        cleaned = _CHINESE_SEASON.sub(" ", cleaned, count=1)
    cleaned = re.sub(r"[._]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_[](){}")
    return cleaned or parent_name


def _unique_ints(values: Iterable[int]) -> tuple[int, ...]:
    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        number = int(value)
        if number in seen:
            continue
        seen.add(number)
        result.append(number)
    return tuple(result)
