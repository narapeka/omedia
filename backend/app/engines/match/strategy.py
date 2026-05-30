from __future__ import annotations

from dataclasses import dataclass
from app.domain.media import MediaType
from app.domain.match import ConfidenceLevel, MatchHint, TitleHint
from app.domain.match import (
    HintSource,
    MatchContext,
    TMDBCandidate,
    TMDBSearchPage,
    TitleKind,
)

from .confidence import confidence_rank, normalize_title


@dataclass(frozen=True)
class SearchStrategy:
    title: str
    title_kind: TitleKind
    hint_source: HintSource
    group: str
    search_year: int | None
    validation_year: int | None
    language: str
    context: MatchContext | None = None
    search_year_suppressed: bool = False
    page: int = 1


@dataclass(frozen=True)
class StrategyEvaluation:
    strategy: SearchStrategy
    page: TMDBSearchPage
    selected_candidate: TMDBCandidate | None
    confidence: ConfidenceLevel
    local_confidence: ConfidenceLevel = ConfidenceLevel.NONE
    tv_year_validation: dict[str, object] | None = None
    confidence_rule: str | None = None
    year_match: str | None = None
    evaluated_count: int = 0
    unique_candidate_count: int = 0
    selected_candidate_index: int | None = None
    detail_failures: int = 0
    stopped_on_high: bool = False


def strategy_summary(evaluation: StrategyEvaluation) -> dict[str, object]:
    candidate = evaluation.selected_candidate
    values: dict[str, object] = {
        **strategy_values(evaluation.strategy),
        "shallow_count": len(evaluation.page.results),
        "candidate_count": len(evaluation.page.results),
        "evaluated_count": evaluation.evaluated_count,
        "unique_candidate_count": evaluation.unique_candidate_count,
        "total_pages": evaluation.page.total_pages,
        "total_results": evaluation.page.total_results,
        "selected_tmdb_id": candidate.tmdb_id if candidate else None,
        "selected_candidate_index": evaluation.selected_candidate_index,
        "confidence": evaluation.confidence.value,
        "local_confidence": evaluation.local_confidence.value,
        "confidence_rule": evaluation.confidence_rule,
        "year_match": evaluation.year_match,
        "detail_failures": evaluation.detail_failures,
        "stopped_on_high": evaluation.stopped_on_high,
    }
    if evaluation.tv_year_validation is not None:
        values["tv_year_validation"] = evaluation.tv_year_validation
    return values


def strategy_values(strategy: SearchStrategy) -> dict[str, object]:
    values: dict[str, object] = {
        "title": strategy.title,
        "title_kind": strategy.title_kind.value,
        "hint_source": strategy.hint_source.value,
        "group": strategy.group,
        "search_year": strategy.search_year,
        "validation_year": strategy.validation_year,
        "language": strategy.language,
        "page": strategy.page,
        "search_year_suppressed": strategy.search_year_suppressed,
    }
    tv_context = strategy.context.tv if strategy.context else None
    if tv_context is not None:
        values["tv_year_fact_count"] = len(tv_context.year_facts)
        values["tv_year_scopes"] = [fact.scope.value for fact in tv_context.year_facts]
    return values


def best_evaluation(
    current: StrategyEvaluation | None,
    candidate: StrategyEvaluation,
) -> StrategyEvaluation | None:
    if candidate.selected_candidate is None:
        return current
    if current is None or confidence_rank(candidate.confidence) > confidence_rank(current.confidence):
        return candidate
    return current


def build_search_strategies(hint: MatchHint, media_type: MediaType) -> list[SearchStrategy]:
    title_hints = _automatic_title_hints(hint.titles)
    if not title_hints:
        return []
    context = hint.context
    year_groups = _strategy_year_groups(hint, media_type, context)
    strategies: list[SearchStrategy] = []
    seen: set[tuple[str, str, int | None, str, int]] = set()
    for group_suffix, search_year, validation_year, search_year_suppressed in year_groups:
        for title_hint in title_hints:
            language = _automatic_language(title_hint.kind)
            group = f"{title_hint.kind.value}_{group_suffix}"
            key = (
                media_type.value,
                normalize_title(title_hint.value),
                search_year,
                language,
                1,
            )
            if key in seen:
                continue
            seen.add(key)
            strategies.append(
                SearchStrategy(
                    title=title_hint.value.strip(),
                    title_kind=title_hint.kind,
                    hint_source=title_hint.source,
                    group=group,
                    search_year=search_year,
                    validation_year=validation_year,
                    language=language,
                    context=context,
                    search_year_suppressed=search_year_suppressed,
                    page=1,
                )
            )
    return strategies


def requires_deferred_tv_year_validation(strategy: SearchStrategy) -> bool:
    tv_context = strategy.context.tv if strategy.context else None
    return bool(tv_context and tv_context.deferred_year_facts)


def _automatic_title_hints(titles: tuple[TitleHint, ...]) -> list[TitleHint]:
    title_order = {TitleKind.CHINESE: 0, TitleKind.ENGLISH: 1}
    return sorted(
        (
            title
            for title in titles
            if title.source == HintSource.LLM
            and title.kind in title_order
            and title.value.strip()
        ),
        key=lambda title: title_order[title.kind],
    )


def _strategy_year_groups(
    hint: MatchHint,
    media_type: MediaType,
    context: MatchContext | None,
) -> tuple[tuple[str, int | None, int | None, bool], ...]:
    if media_type == MediaType.TV:
        tv_context = context.tv if context else None
        if tv_context is not None:
            show_year = tv_context.search_year
            if show_year is not None:
                return (
                    ("with_year", show_year, show_year, False),
                    ("without_year", None, show_year, True),
                )
            if tv_context.has_year_facts:
                return (("without_year", None, None, True),)
        if hint.year is not None:
            return (
                ("without_year", None, hint.year, True),
                ("with_year", hint.year, hint.year, False),
            )
        return (("without_year", None, None, False),)

    if hint.year is not None:
        return (
            ("with_year", hint.year, hint.year, False),
            ("without_year", None, hint.year, True),
        )
    return (("without_year", None, None, False),)


def _automatic_language(kind: TitleKind) -> str:
    if kind == TitleKind.CHINESE:
        return "zh-CN"
    if kind == TitleKind.ENGLISH:
        return "en-US"
    raise ValueError(f"Unsupported automatic title kind: {kind.value}")
