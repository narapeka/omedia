from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import tempfile

import yaml
from fastapi.testclient import TestClient

from app.domain.activity import ActivityEvent
from app.domain.match import MatchHint, TMDBCandidate, TMDBSearchPage, TMDBSearchResult
from app.domain.tv import EpisodeLLMResult
from app.domain.media import MediaExtensionPolicy
from app.domain.tv import TVEpisodeCatalog
from app.boot.runtime import create_runtime_context
from app.main import create_app
from app.services.config.values import OrganizeSettings, StartupSettings

TEST_MEDIA_EXTENSIONS = MediaExtensionPolicy(
    video=frozenset(
        {
            ".mp4",
            ".mkv",
            ".avi",
            ".mov",
            ".wmv",
            ".flv",
            ".webm",
            ".m4v",
            ".ts",
            ".m2ts",
            ".f4v",
            ".mpg",
            ".mpeg",
        }
    ),
    subtitle=frozenset(
        {
            ".srt",
            ".ass",
            ".ssa",
            ".vtt",
            ".sub",
            ".idx",
            ".sup",
            ".pgs",
        }
    ),
    sidecar=frozenset(
        {
            ".nfo",
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".txt",
        }
    ),
)


def make_startup_settings(**kwargs) -> StartupSettings:
    kwargs.setdefault("organize", OrganizeSettings(extensions=TEST_MEDIA_EXTENSIONS))
    return StartupSettings(**kwargs)


def make_common_config(
    *,
    min_non_subtitle_file_size_mb: int = 0,
    tmdb: dict[str, object] | None = None,
    llm: dict[str, object] | None = None,
    watch: dict[str, object] | None = None,
) -> dict[str, object]:
    config: dict[str, object] = {
        "organize": {
            "extensions": {"video": [".mkv"], "subtitle": [".srt"], "sidecar": [".nfo"]},
            "min_non_subtitle_file_size_mb": min_non_subtitle_file_size_mb,
        },
        "tmdb": tmdb or {"api_key": ""},
        "llm": llm or {"api_key": ""},
    }
    if watch is not None:
        config["watch"] = watch
    return config


class RuntimeApiFixture:
    def __init__(self, *, common: dict[str, object] | None = None) -> None:
        self.common = common

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.common_path = self.root / "common.yaml"
        self.common_path.write_text(
            yaml.safe_dump(self.common or make_common_config(), sort_keys=False),
            encoding="utf-8",
        )
        self.runtime = create_runtime_context(common_path=self.common_path, db_path=self.root / "state.sqlite")
        self.client = TestClient(create_app(runtime=self.runtime))
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        try:
            self.runtime.stop_automations()
        finally:
            self.runtime.store.close()
            self.temp.cleanup()


class FakeActivityStore:
    def __init__(
        self,
        events: Sequence[ActivityEvent] | None = None,
        *,
        by_source: Sequence[ActivityEvent] | None = None,
        by_target: Sequence[ActivityEvent] | None = None,
    ) -> None:
        self.events = list(events or [])
        self.by_source = list(by_source or [])
        self.by_target = list(by_target or [])
        self.calls: list[dict] = []

    def save_activity_event(self, event: ActivityEvent) -> None:
        self.events.append(event)

    def list_activity_events(self, **kwargs):
        self.calls.append(kwargs)
        if "entity_source" in kwargs:
            return self.by_source
        if "entity_target" in kwargs:
            return self.by_target
        return self.events


class FakeRequester:
    def __init__(self, responses: Sequence[bytes | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def read(self, request, *, timeout_seconds: float):
        call = {
            "url": request.full_url,
            "headers": dict(request.header_items()),
            "timeout_seconds": timeout_seconds,
        }
        if request.data is not None:
            call["payload"] = json.loads(request.data.decode("utf-8"))
        self.calls.append(call)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeTMDB:
    def __init__(self) -> None:
        self.by_id = {}
        self.details = {}
        self.search_results = []
        self.search_pages = {}
        self.search_calls = []
        self.detail_calls = []
        self.season_years = {}
        self.season_year_calls = []

    def get_by_id(self, media_type, tmdb_id):
        return self.by_id.get((media_type, tmdb_id))

    def search_page(self, media_type, title, year, language, page):
        self.search_calls.append(
            {"media_type": media_type, "title": title, "year": year, "language": language, "page": page}
        )
        value = self.search_pages.get((title, year, language, page), self.search_results)
        if isinstance(value, TMDBSearchPage):
            return self._search_page_from_results(
                value.results,
                page=value.page,
                total_pages=value.total_pages,
                total_results=value.total_results,
                language=language,
            )
        return TMDBSearchPage(
            results=tuple(self._search_result(item, language) for item in value),
            page=page,
            total_pages=1 if value else 0,
            total_results=len(value),
        )

    def load_candidate_details(self, media_type, tmdb_id, language, fallback_search_result):
        self.detail_calls.append((media_type, int(tmdb_id), language))
        return (
            self.details.get((media_type, int(tmdb_id), language))
            or self.details.get((media_type, int(tmdb_id)))
            or self.by_id.get((media_type, int(tmdb_id)))
            or fallback_search_result.to_candidate()
        )

    def _search_page_from_results(self, results, *, page, total_pages, total_results, language):
        coerced = tuple(self._search_result(item, language) for item in results)
        return TMDBSearchPage(
            results=coerced,
            page=page,
            total_pages=total_pages,
            total_results=total_results,
        )

    def _search_result(self, item, language):
        if isinstance(item, TMDBSearchResult):
            return item
        if isinstance(item, TMDBCandidate):
            self.details.setdefault((item.media_type, item.tmdb_id, language), item)
            return TMDBSearchResult(
                item.tmdb_id,
                item.media_type,
                item.title,
                original_title=item.original_title,
                year=item.year,
                metadata=dict(item.metadata),
            )
        return item

    def get_tv_season_years(self, tmdb_id, season_numbers, languages):
        seasons = tuple(int(season) for season in season_numbers)
        self.season_year_calls.append({"tmdb_id": tmdb_id, "seasons": seasons, "languages": tuple(languages)})
        return {
            season: int(self.season_years[(tmdb_id, season)])
            for season in seasons
            if (tmdb_id, season) in self.season_years
        }


class FixedLLMHintExtractor:
    def __init__(self, hint: MatchHint):
        self.hint = hint
        self.single_calls = 0

    def extract_hint(self, candidate):
        self.single_calls += 1
        return self.hint

    def extract_hints(self, candidates, *, batch_size=50):
        return {candidate.id: self.hint for candidate in candidates}


class FixedMediaNameExtractor:
    def __init__(self, hint: MatchHint):
        self.hint = hint

    def extract(self, candidate):
        return self.hint


class BatchLLMHintExtractor:
    def __init__(self, hints: Mapping[str, MatchHint]):
        self.hints = dict(hints)
        self.batch_calls = []
        self.single_calls = 0

    def extract_hint(self, candidate):
        self.single_calls += 1
        return self.hints.get(candidate.id, MatchHint())

    def extract_hints(self, candidates, *, batch_size=50):
        self.batch_calls.append((tuple(candidate.id for candidate in candidates), batch_size))
        return {
            candidate.id: self.hints[candidate.id]
            for candidate in candidates
            if candidate.id in self.hints
        }


class FakeTVEpisodeExtractor:
    def __init__(
        self,
        results: Mapping[str, EpisodeLLMResult | Mapping[str, object]] | None = None,
        *,
        error: Exception | None = None,
    ):
        self.results = {
            key: _episode_llm_result(key, value)
            for key, value in (results or {}).items()
        }
        self.error = error
        self.calls: list[dict[str, object]] = []

    @property
    def requested_keys(self) -> list[str]:
        return [
            key
            for call in self.calls
            for key in call["filenames"]
        ]

    def extract_episodes(
        self,
        *,
        show_name: str,
        filenames: Sequence[str],
        tmdb_context: str = "",
        chunk_size: int = 100,
    ) -> dict[str, EpisodeLLMResult]:
        keys = list(filenames)
        self.calls.append(
            {
                "show_name": show_name,
                "filenames": keys,
                "tmdb_context": tmdb_context,
                "chunk_size": chunk_size,
            }
        )
        if self.error is not None:
            raise self.error
        allowed = set(keys)
        return {
            key: value
            for key, value in self.results.items()
            if key in allowed
        }


class FakeTVEpisodeCatalogProvider:
    def __init__(self, catalog=None):
        self.catalog = catalog
        self.calls: list[dict[str, object]] = []

    def tv_episode_catalog(self, *, tmdb_id: int | None):
        self.calls.append({"tmdb_id": tmdb_id})
        return self.catalog

    def tv_episode_titles(self, *, tmdb_id: int | None, season_numbers):
        self.calls.append({"tmdb_id": tmdb_id, "season_numbers": tuple(season_numbers)})
        if self.catalog is None:
            return {}
        if isinstance(self.catalog, TVEpisodeCatalog):
            return {
                int(season): dict(self.catalog.seasons.get(int(season), {}))
                for season in season_numbers
                if self.catalog.seasons.get(int(season))
            }
        return {
            int(season): dict(self.catalog.get(int(season), {}))
            for season in season_numbers
            if self.catalog.get(int(season))
        }


def _episode_llm_result(key: str, value: EpisodeLLMResult | Mapping[str, object]) -> EpisodeLLMResult:
    if isinstance(value, EpisodeLLMResult):
        return value
    filename = str(value.get("filename") or key)
    return EpisodeLLMResult(
        filename=filename,
        season=int(value["season"]),
        episode=int(value["episode"]),
        end_episode=int(value["end_episode"]) if value.get("end_episode") is not None else None,
    )
