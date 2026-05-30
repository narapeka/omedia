from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.domain.media import MediaType


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class YearMatch(str, Enum):
    EXACT = "exact"
    FUZZY = "fuzzy"
    MISSING = "missing"
    MISMATCH = "mismatch"


@dataclass(frozen=True)
class MatchEvidence:
    source: str
    confidence: ConfidenceLevel
    values: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None


@dataclass
class MatchResult:
    candidate_id: str
    media_type: MediaType
    confidence: ConfidenceLevel
    title: str | None = None
    original_title: str | None = None
    year: int | None = None
    tmdb_id: int | None = None
    selected_external_id: str | None = None
    evidence: list[MatchEvidence] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence == ConfidenceLevel.HIGH


class TVYearScope(str, Enum):
    SHOW_YEAR = "show_year"
    SEASON_YEAR = "season_year"
    SHOW_OR_SEASON_YEAR = "show_or_season_year"


class TVYearFactSource(str, Enum):
    CANDIDATE_FOLDER = "candidate_folder"
    DIRECT_ROOT_SEGMENT = "direct_root_segment"
    SEASON_SUBFOLDER = "season_subfolder"


@dataclass(frozen=True)
class TVYearFact:
    year: int
    scope: TVYearScope
    season: int | None = None
    source: TVYearFactSource = TVYearFactSource.CANDIDATE_FOLDER
    label: str = ""

    def evidence_values(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "scope": self.scope.value,
            "season": self.season,
            "source": self.source.value,
            "label": self.label,
        }


@dataclass(frozen=True)
class TVSourceContext:
    structure: str | None
    show_title_source: str
    year_facts: tuple[TVYearFact, ...] = ()
    detected_seasons: tuple[int, ...] = ()

    @property
    def has_year_facts(self) -> bool:
        return bool(self.year_facts)

    @property
    def show_years(self) -> tuple[TVYearFact, ...]:
        return tuple(fact for fact in self.year_facts if fact.scope == TVYearScope.SHOW_YEAR)

    @property
    def deferred_year_facts(self) -> tuple[TVYearFact, ...]:
        return tuple(fact for fact in self.year_facts if fact.scope != TVYearScope.SHOW_YEAR)

    @property
    def search_year(self) -> int | None:
        years = self.show_years
        return years[0].year if years else None

    @property
    def suppresses_year_search(self) -> bool:
        return any(fact.scope != TVYearScope.SHOW_YEAR for fact in self.year_facts)

    def evidence_values(self) -> dict[str, Any]:
        return {
            "structure": self.structure,
            "show_title_source": self.show_title_source,
            "detected_seasons": list(self.detected_seasons),
            "year_facts": [fact.evidence_values() for fact in self.year_facts],
        }


@dataclass(frozen=True)
class MatchContext:
    media_type: MediaType
    tv: TVSourceContext | None = None

    def evidence_values(self) -> dict[str, Any]:
        return {
            "media_type": self.media_type.value,
            "tv": self.tv.evidence_values() if self.tv else None,
        }


class TitleKind(str, Enum):
    SOURCE = "source"
    CHINESE = "chinese"
    ENGLISH = "english"


class HintSource(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"


@dataclass(frozen=True)
class TitleHint:
    value: str
    kind: TitleKind
    source: HintSource


@dataclass(frozen=True)
class MatchHint:
    titles: tuple[TitleHint, ...] = ()
    year: int | None = None
    tmdb_id: int | None = None
    context: MatchContext | None = None

    @property
    def primary_title(self) -> str | None:
        return self.titles[0].value if self.titles else None

    @property
    def has_identity(self) -> bool:
        return bool(self.tmdb_id or self.titles)


@dataclass(frozen=True)
class TMDBCandidate:
    tmdb_id: int
    media_type: MediaType
    title: str
    original_title: str | None = None
    year: int | None = None
    alternative_titles: list[dict[str, str]] = field(default_factory=list)
    translations: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def known_titles(self) -> list[str]:
        return _unique_titles(
            [
                self.title,
                self.original_title,
                *(item.get("title") for item in self.alternative_titles),
                *(item.get("title") for item in self.translations),
            ]
        )


@dataclass(frozen=True)
class TMDBSearchResult:
    tmdb_id: int
    media_type: MediaType
    title: str
    original_title: str | None = None
    year: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_candidate(self) -> TMDBCandidate:
        metadata = {
            "media_type": self.media_type.value,
            "title": self.title,
            "original_title": self.original_title,
            "year": self.year,
            "release_year": self.year,
            "tmdb_id": self.tmdb_id,
            **dict(self.metadata),
        }
        return TMDBCandidate(
            tmdb_id=self.tmdb_id,
            media_type=self.media_type,
            title=self.title,
            original_title=self.original_title,
            year=self.year,
            metadata=metadata,
        )


@dataclass(frozen=True)
class TMDBSearchPage:
    results: tuple[TMDBSearchResult, ...] = ()
    page: int = 1
    total_pages: int = 0
    total_results: int = 0


def _unique_titles(values) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
