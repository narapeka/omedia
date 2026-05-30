from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.domain.match import ConfidenceLevel, YearMatch
from app.domain.match import HintSource, TMDBCandidate, TitleKind


LOW_AMBIGUITY_RESULT_LIMIT = 3


@dataclass(frozen=True)
class ConfidenceAssessment:
    confidence: ConfidenceLevel
    title_matched: bool
    known_title_matched: bool = False
    year_match: YearMatch = YearMatch.MISSING
    rule: str = "low_selected_candidate"


@dataclass(frozen=True)
class ConfidenceContext:
    source_name: str
    requested_title: str | None
    requested_title_kind: TitleKind | None
    hint_source: HintSource | None
    requested_year: int | None
    year_match: YearMatch
    all_results_count: int
    deferred_tv_year_validation_required: bool = False
    tv_year_validation: dict[str, object] | None = None


class MatchConfidenceEvaluator:
    def assess(
        self,
        candidate: TMDBCandidate,
        *,
        source_name: str,
        requested_title: str | None,
        requested_year: int | None,
        all_results_count: int,
        requested_title_kind: TitleKind | None = None,
        hint_source: HintSource | None = None,
        year_match: YearMatch | None = None,
        deferred_tv_year_validation_required: bool = False,
        tv_year_validation: dict[str, object] | None = None,
    ) -> ConfidenceAssessment:
        return self.assess_with_context(
            candidate,
            ConfidenceContext(
                source_name=source_name,
                requested_title=requested_title,
                requested_title_kind=requested_title_kind,
                hint_source=hint_source,
                requested_year=requested_year,
                year_match=year_match or classify_year_match(requested_year, candidate.year),
                all_results_count=all_results_count,
                deferred_tv_year_validation_required=deferred_tv_year_validation_required,
                tv_year_validation=tv_year_validation,
            ),
        )

    def assess_with_context(
        self,
        candidate: TMDBCandidate | None,
        context: ConfidenceContext,
    ) -> ConfidenceAssessment:
        if candidate is None:
            return ConfidenceAssessment(
                ConfidenceLevel.NONE,
                title_matched=False,
                year_match=context.year_match,
                rule="no_selected_candidate",
            )

        title_matched = title_matches_source(candidate.known_titles(), context.source_name)
        normalized_titles = {normalize_title(title) for title in candidate.known_titles()}
        known_title_matched = bool(
            context.requested_title and normalize_title(context.requested_title) in normalized_titles
        )

        # High-confidence behavior is intentionally evaluated as its own first
        # branch: source-name evidence, exact or one-year-off year agreement,
        # or pending scoped TV year validation, then the existing single-result
        # or exact requested-title gates.
        if title_matched and _year_allows_high(context):
            if context.all_results_count == 1:
                return ConfidenceAssessment(
                    ConfidenceLevel.HIGH,
                    title_matched=True,
                    known_title_matched=known_title_matched,
                    year_match=context.year_match,
                    rule="source_title_single_result",
                )
            if known_title_matched:
                return ConfidenceAssessment(
                    ConfidenceLevel.HIGH,
                    title_matched=True,
                    known_title_matched=True,
                    year_match=context.year_match,
                    rule="source_title_exact_requested_title",
                )

        if context.year_match == YearMatch.MISMATCH:
            return ConfidenceAssessment(
                ConfidenceLevel.LOW,
                title_matched=title_matched,
                known_title_matched=known_title_matched,
                year_match=context.year_match,
                rule="year_mismatch",
            )

        if known_title_matched and _is_non_source_title_hint(context):
            return ConfidenceAssessment(
                ConfidenceLevel.MEDIUM,
                title_matched=title_matched,
                known_title_matched=True,
                year_match=context.year_match,
                rule="non_source_exact_known_title",
            )

        if context.all_results_count == 1:
            return ConfidenceAssessment(
                ConfidenceLevel.MEDIUM,
                title_matched=title_matched,
                known_title_matched=known_title_matched,
                year_match=context.year_match,
                rule="single_result_after_high_failed",
            )

        if (
            known_title_matched
            and context.year_match == YearMatch.MISSING
            and 0 < context.all_results_count <= LOW_AMBIGUITY_RESULT_LIMIT
        ):
            return ConfidenceAssessment(
                ConfidenceLevel.MEDIUM,
                title_matched=title_matched,
                known_title_matched=True,
                year_match=context.year_match,
                rule="exact_title_missing_year_low_ambiguity",
            )

        return ConfidenceAssessment(
            ConfidenceLevel.LOW,
            title_matched=title_matched,
            known_title_matched=known_title_matched,
            year_match=context.year_match,
            rule="low_selected_candidate",
        )

    def evaluate(
        self,
        candidate: TMDBCandidate,
        *,
        source_name: str,
        requested_title: str | None,
        requested_year: int | None,
        all_results_count: int,
    ) -> ConfidenceLevel:
        return self.assess(
            candidate,
            source_name=source_name,
            requested_title=requested_title,
            requested_year=requested_year,
            all_results_count=all_results_count,
        ).confidence


def classify_year_match(requested_year: int | None, candidate_year: int | None) -> YearMatch:
    if requested_year is None or candidate_year is None:
        return YearMatch.MISSING
    difference = abs(int(requested_year) - int(candidate_year))
    if difference == 0:
        return YearMatch.EXACT
    if difference == 1:
        return YearMatch.FUZZY
    return YearMatch.MISMATCH


def title_matches_source(titles: Sequence[str], source_name: str) -> bool:
    normalized_source = normalize_title(source_name)
    return any(normalize_title(title) in normalized_source for title in titles if title)


def normalize_title(value: str) -> str:
    return " ".join(
        value.lower()
        .replace(".", " ")
        .replace("_", " ")
        .replace("-", " ")
        .replace(":", " ")
        .split()
    )


def confidence_rank(confidence: ConfidenceLevel) -> int:
    return {
        ConfidenceLevel.HIGH: 3,
        ConfidenceLevel.MEDIUM: 2,
        ConfidenceLevel.LOW: 1,
        ConfidenceLevel.NONE: 0,
    }[confidence]


def _year_allows_high(context: ConfidenceContext) -> bool:
    return context.year_match in {YearMatch.EXACT, YearMatch.FUZZY} or (
        context.year_match == YearMatch.MISSING and context.deferred_tv_year_validation_required
    )


def _is_non_source_title_hint(context: ConfidenceContext) -> bool:
    return context.requested_title_kind is not None and context.requested_title_kind != TitleKind.SOURCE
