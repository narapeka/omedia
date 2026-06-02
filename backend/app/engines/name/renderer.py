from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.core.path import sanitize_filename_component


@dataclass(frozen=True)
class NamingRenderResult:
    relative_path: Path | None
    warnings: list[str] = field(default_factory=list)

    @property
    def renderable(self) -> bool:
        return self.relative_path is not None


@dataclass(frozen=True)
class MovieNamingInput:
    title: str | None
    year: int | None
    tmdb_id: int | str | None
    extension: str
    part_token: str | None = None
    tag_suffix: str | None = None


@dataclass(frozen=True)
class TVNamingInput:
    title: str | None
    year: int | None
    tmdb_id: int | str | None
    season: int | None
    episode: int | None
    episode_title: str | None
    extension: str
    end_episode: int | None = None
    tag_suffix: str | None = None


def render_movie_path(value: MovieNamingInput) -> NamingRenderResult:
    warnings: list[str] = []
    title = _clean_component("title", value.title, warnings)
    year = _optional_int("year", value.year, warnings)
    tmdb_id = _optional_text("tmdb_id", value.tmdb_id, warnings)
    extension = _extension(value.extension)

    name = _title_with_year(title, year)
    folder_parts = [name]
    if tmdb_id:
        folder_parts.append(f"{{tmdb-{tmdb_id}}}")
    folder = _clean_component("movie_folder", " ".join(folder_parts), warnings)
    if value.tag_suffix:
        folder = f"{folder} {value.tag_suffix}"
    filename_parts = [name]
    if value.part_token is not None:
        part_token = _optional_component("movie_part_token", value.part_token, warnings)
        if part_token:
            filename_parts.append(part_token)
    filename = _clean_component("movie_filename", " - ".join(filename_parts), warnings) + extension
    return NamingRenderResult(Path(folder) / filename, warnings)


def render_tv_path(value: TVNamingInput) -> NamingRenderResult:
    warnings: list[str] = []
    title = _clean_component("title", value.title, warnings)
    year = _optional_int("year", value.year, warnings)
    tmdb_id = _optional_text("tmdb_id", value.tmdb_id, warnings)
    season = _required_int("season", value.season, warnings)
    episode = _required_int("episode", value.episode, warnings)
    episode_title = _optional_component("episode_title", value.episode_title, warnings)
    extension = _extension(value.extension)
    if season is None or episode is None:
        return NamingRenderResult(None, warnings)

    show_name = _title_with_year(title, year)
    folder_parts = [show_name]
    if tmdb_id:
        folder_parts.append(f"{{tmdb-{tmdb_id}}}")
    show_folder = _clean_component("show_folder", " ".join(folder_parts), warnings)
    if value.tag_suffix:
        show_folder = f"{show_folder} {value.tag_suffix}"
    season_folder = "Specials" if season == 0 else f"Season {season}"
    code = f"S{season:02d}E{episode:02d}"
    if value.end_episode:
        code = f"{code}-E{value.end_episode:02d}"
    filename_parts = [title, code]
    if episode_title:
        filename_parts.append(episode_title)
    filename = _clean_component("episode_filename", " - ".join(filename_parts), warnings) + extension
    return NamingRenderResult(Path(show_folder) / season_folder / filename, warnings)


def _title_with_year(title: str, year: int | None) -> str:
    return f"{title} ({year})" if year else title


def _clean_component(label: str, value: str | None, warnings: list[str]) -> str:
    raw = value or "Untitled"
    cleaned = sanitize_filename_component(str(raw), replacement=".")
    if cleaned != raw:
        warnings.append(f"{label}_sanitized")
    return cleaned


def _optional_component(label: str, value: str | None, warnings: list[str]) -> str | None:
    if not value:
        warnings.append(f"missing_{label}")
        return None
    return _clean_component(label, value, warnings)


def _optional_text(label: str, value: int | str | None, warnings: list[str]) -> str | None:
    if value is None or str(value).strip() == "":
        warnings.append(f"missing_{label}")
        return None
    return str(value).strip()


def _optional_int(label: str, value: int | None, warnings: list[str]) -> int | None:
    if value is None:
        warnings.append(f"missing_{label}")
        return None
    return int(value)


def _required_int(label: str, value: int | None, warnings: list[str]) -> int | None:
    if value is None:
        warnings.append(f"missing_{label}")
        return None
    return int(value)


def _extension(value: str) -> str:
    extension = value.strip().lower()
    if not extension:
        return ""
    return extension if extension.startswith(".") else f".{extension}"
