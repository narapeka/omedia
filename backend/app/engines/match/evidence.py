from __future__ import annotations

from typing import Sequence

from app.domain.match import ConfidenceLevel
from app.domain.match import MatchContext, MatchEvidence, MatchHint

from .strategy import StrategyEvaluation, strategy_values


def search_evidence(
    search_source: str,
    selected: StrategyEvaluation,
    attempts: Sequence[dict[str, object]],
    pagination_reason: str,
) -> MatchEvidence:
    candidate = selected.selected_candidate
    return MatchEvidence(
        f"{search_source}_tmdb_search",
        selected.confidence,
        {
            "attempted_strategies": list(attempts),
            "attempted_strategy_count": len(attempts),
            "selected_strategy": strategy_values(selected.strategy) if candidate else None,
            "selected_tmdb_id": candidate.tmdb_id if candidate else None,
            "selected_candidate_index": selected.selected_candidate_index,
            "selected_evaluated_count": selected.evaluated_count,
            "selected_shallow_count": len(selected.page.results),
            "stopped_on_high": selected.stopped_on_high,
            "pagination_reason": pagination_reason,
            "selected_tv_year_validation": selected.tv_year_validation,
        },
    )


def hint_evidence(source: str, hint: MatchHint) -> MatchEvidence:
    return MatchEvidence(
        source=source,
        confidence=ConfidenceLevel.MEDIUM if hint.has_identity else ConfidenceLevel.LOW,
        values={
            "titles": [
                {
                    "value": title.value,
                    "kind": title.kind.value,
                    "source": title.source.value,
                }
                for title in hint.titles
            ],
            "year": hint.year,
            "tmdb_id": hint.tmdb_id,
        },
    )


def match_context_evidence(context: MatchContext, *, source_display_name: str) -> MatchEvidence:
    values = context.evidence_values()
    values["source_display_name"] = source_display_name
    return MatchEvidence(
        source="match_context",
        confidence=ConfidenceLevel.MEDIUM if context.tv and context.tv.show_title_source else ConfidenceLevel.LOW,
        values=values,
    )


def merge_hints(source_hint: MatchHint, llm_hint: MatchHint) -> MatchHint:
    return MatchHint(
        titles=(*source_hint.titles, *llm_hint.titles),
        year=llm_hint.year if llm_hint.year is not None else source_hint.year,
        tmdb_id=llm_hint.tmdb_id if llm_hint.tmdb_id is not None else source_hint.tmdb_id,
        context=source_hint.context or llm_hint.context,
    )
