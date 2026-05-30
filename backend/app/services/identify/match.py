from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from typing import Sequence

from app.core.error import MatchError
from app.domain.match import ConfidenceLevel
from app.domain.media import MediaType
from app.domain.match import HintSource, MatchEvidence, MatchHint, MatchResult, TMDBCandidate, TMDBSearchPage, TMDBSearchResult, TitleHint, TitleKind
from app.domain.media import MediaCandidate
from app.engines.match.confidence import MatchConfidenceEvaluator, classify_year_match, confidence_rank
from app.engines.match.evidence import hint_evidence, match_context_evidence, merge_hints, search_evidence
from app.engines.match.strategy import (
    SearchStrategy,
    StrategyEvaluation,
    best_evaluation,
    build_search_strategies,
    requires_deferred_tv_year_validation,
    strategy_summary,
)
from app.engines.match.tv import validate_year_facts
from app.services.identify.protocol import LLMHintExtractor, MediaNameExtractor, TMDBLookupClient


class MatchService:
    def __init__(
        self,
        tmdb: TMDBLookupClient,
        *,
        media_name_extractor: MediaNameExtractor | None = None,
        llm_extractor: LLMHintExtractor,
        confidence_evaluator: MatchConfidenceEvaluator | None = None,
        languages: Sequence[str] = ("zh-CN", "en-US"),
        max_search_pages: int = 3,
    ):
        self.tmdb = tmdb
        self.media_name_extractor = media_name_extractor
        self.llm_extractor = llm_extractor
        self.confidence_evaluator = confidence_evaluator or MatchConfidenceEvaluator()
        self.languages = tuple(languages)
        self.max_search_pages = max(1, int(max_search_pages))

    def match(self, candidate: MediaCandidate) -> MatchResult:
        hint, evidence, search_source = self._extract_hint(candidate)
        return self._match_with_hint(candidate, hint, evidence=evidence, search_source=search_source)

    def match_batch(
        self,
        candidates: Sequence[MediaCandidate],
        *,
        llm_batch_size: int = 50,
        max_workers: int | None = None,
    ) -> dict[str, MatchResult]:
        batch_hints, attempted_ids = self._batch_llm_hints(candidates, batch_size=llm_batch_size)
        workers = _batch_worker_count(len(candidates), max_workers)
        if workers <= 1:
            return {
                candidate.id: self._match_batch_candidate(candidate, batch_hints, attempted_ids)
                for candidate in candidates
            }

        unordered: dict[str, MatchResult] = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._match_batch_candidate, candidate, batch_hints, attempted_ids): candidate.id
                for candidate in candidates
            }
            for future in as_completed(futures):
                candidate_id = futures[future]
                unordered[candidate_id] = future.result()
        return {candidate.id: unordered[candidate.id] for candidate in candidates}

    def _match_batch_candidate(
        self,
        candidate: MediaCandidate,
        batch_hints: dict[str, MatchHint],
        attempted_ids: set[str],
    ) -> MatchResult:
        hint, evidence, search_source = self._extract_hint(
            candidate,
            prefetched_llm_hints=batch_hints,
            llm_attempted_ids=attempted_ids,
        )
        return self._match_with_hint(
            candidate,
            hint,
            evidence=evidence,
            search_source=search_source,
        )

    def _match_with_hint(
        self,
        candidate: MediaCandidate,
        hint: MatchHint,
        *,
        evidence: list[MatchEvidence],
        search_source: str,
    ) -> MatchResult:
        if hint.tmdb_id:
            tmdb_candidate = self.tmdb.get_by_id(candidate.media_type, hint.tmdb_id)
            if tmdb_candidate:
                evidence.append(
                    MatchEvidence(
                        source=f"{search_source}_tmdb_direct_id",
                        confidence=ConfidenceLevel.HIGH,
                        values={"tmdb_id": tmdb_candidate.tmdb_id, "title": tmdb_candidate.title},
                    )
                )
                return self._result(candidate, tmdb_candidate, ConfidenceLevel.HIGH, evidence)

        strategies = build_search_strategies(hint, candidate.media_type)
        if not strategies:
            evidence.append(
                MatchEvidence(
                    source=f"{search_source}_tmdb_search",
                    confidence=ConfidenceLevel.NONE,
                    values={
                        "no_title_search_skipped": True,
                        "reason": "no_usable_llm_chinese_or_english_title",
                    },
                )
            )
            return MatchResult(
                candidate_id=candidate.id,
                media_type=candidate.media_type,
                confidence=ConfidenceLevel.NONE,
                evidence=evidence,
            )

        attempts: list[dict[str, object]] = []
        best_overall: StrategyEvaluation | None = None
        best_page_eligible: StrategyEvaluation | None = None

        for strategy in strategies:
            evaluation = self._execute_strategy(candidate, strategy)
            attempts.append(strategy_summary(evaluation))
            best_overall = best_evaluation(best_overall, evaluation)
            if best_page_eligible is None and evaluation.page.total_pages > evaluation.page.page:
                best_page_eligible = evaluation
            if evaluation.confidence == ConfidenceLevel.HIGH and evaluation.selected_candidate is not None:
                evidence.append(search_evidence(search_source, evaluation, attempts, "high_confidence_page_one"))
                return self._result(candidate, evaluation.selected_candidate, evaluation.confidence, evidence)

        pagination_reason = "no_page_eligible_strategy"
        if best_page_eligible is not None:
            pagination_reason = "no_additional_pages"
            max_page = min(best_page_eligible.page.total_pages, self.max_search_pages)
            if max_page > best_page_eligible.page.page:
                pagination_reason = "page_bound_reached" if best_page_eligible.page.total_pages > max_page else "pages_exhausted"
                for page_number in range(best_page_eligible.page.page + 1, max_page + 1):
                    strategy = replace(best_page_eligible.strategy, page=page_number)
                    evaluation = self._execute_strategy(candidate, strategy)
                    attempts.append(strategy_summary(evaluation))
                    best_overall = best_evaluation(best_overall, evaluation)
                    if evaluation.confidence == ConfidenceLevel.HIGH and evaluation.selected_candidate is not None:
                        evidence.append(search_evidence(search_source, evaluation, attempts, "high_confidence_extra_page"))
                        return self._result(candidate, evaluation.selected_candidate, evaluation.confidence, evidence)

        if best_overall and best_overall.selected_candidate is not None:
            evidence.append(search_evidence(search_source, best_overall, attempts, pagination_reason))
            return self._result(candidate, best_overall.selected_candidate, best_overall.confidence, evidence)

        unmatched = StrategyEvaluation(
            strategies[0],
            TMDBSearchPage(page=1),
            None,
            ConfidenceLevel.NONE,
        )
        evidence.append(search_evidence(search_source, unmatched, attempts, pagination_reason))
        return MatchResult(candidate.id, candidate.media_type, ConfidenceLevel.NONE, evidence=evidence)

    def _execute_strategy(self, candidate: MediaCandidate, strategy: SearchStrategy) -> StrategyEvaluation:
        page = self.tmdb.search_page(
            candidate.media_type,
            strategy.title,
            strategy.search_year,
            strategy.language,
            strategy.page,
        )
        selected_candidate: TMDBCandidate | None = None
        selected_confidence = ConfidenceLevel.NONE
        selected_local_confidence = ConfidenceLevel.NONE
        selected_validation: dict[str, object] | None = None
        selected_rule: str | None = None
        selected_year_match: str | None = None
        selected_candidate_index: int | None = None
        result_count = max(page.total_results, len(page.results))
        evaluated_count = 0
        unique_candidate_count = 0
        detail_failures = 0
        stopped_on_high = False
        seen_ids: set[int] = set()
        for candidate_index, item in enumerate(page.results, start=1):
            if item.tmdb_id in seen_ids:
                continue
            seen_ids.add(item.tmdb_id)
            unique_candidate_count += 1
            tmdb_candidate, detail_failed = self._load_candidate_details(candidate.media_type, item, strategy.language)
            if tmdb_candidate is None:
                detail_failures += 1
                continue
            if detail_failed:
                detail_failures += 1
            evaluated_count += 1
            year_match = classify_year_match(strategy.validation_year, tmdb_candidate.year)
            assessment = self.confidence_evaluator.assess(
                tmdb_candidate,
                source_name=candidate.display_name,
                requested_title=strategy.title,
                requested_year=strategy.validation_year,
                all_results_count=result_count,
                requested_title_kind=strategy.title_kind,
                hint_source=strategy.hint_source,
                year_match=year_match,
                deferred_tv_year_validation_required=requires_deferred_tv_year_validation(strategy),
            )
            final_confidence, validation = self._apply_deferred_tv_year_validation(
                tmdb_candidate,
                assessment.confidence,
                strategy,
            )
            if selected_candidate is None or confidence_rank(final_confidence) > confidence_rank(selected_confidence):
                selected_candidate = tmdb_candidate
                selected_confidence = final_confidence
                selected_local_confidence = assessment.confidence
                selected_validation = validation
                selected_rule = assessment.rule
                selected_year_match = year_match.value
                selected_candidate_index = candidate_index
            if final_confidence == ConfidenceLevel.HIGH:
                stopped_on_high = True
                break
        return StrategyEvaluation(
            strategy,
            page,
            selected_candidate,
            selected_confidence,
            selected_local_confidence,
            selected_validation,
            selected_rule,
            selected_year_match,
            evaluated_count,
            unique_candidate_count,
            selected_candidate_index,
            detail_failures,
            stopped_on_high,
        )

    def _load_candidate_details(
        self,
        media_type: MediaType,
        search_result: TMDBSearchResult,
        language: str,
    ) -> tuple[TMDBCandidate | None, bool]:
        try:
            candidate = self.tmdb.load_candidate_details(media_type, search_result.tmdb_id, language, search_result)
        except MatchError:
            return search_result.to_candidate(), True
        if candidate is None:
            return search_result.to_candidate(), True
        detail_loaded = candidate.metadata.get("detail_loaded")
        return candidate, detail_loaded is False

    def _apply_deferred_tv_year_validation(
        self,
        tmdb_candidate: TMDBCandidate,
        local_confidence: ConfidenceLevel,
        strategy: SearchStrategy,
    ) -> tuple[ConfidenceLevel, dict[str, object] | None]:
        context = strategy.context
        tv_context = context.tv if context else None
        if (
            local_confidence not in {ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM}
            or tmdb_candidate.media_type != MediaType.TV
            or tv_context is None
            or not tv_context.year_facts
        ):
            return local_confidence, None

        validation = validate_year_facts(
            tmdb_candidate,
            tv_context.year_facts,
            season_year_lookup=lambda seasons: self._tv_season_years(tmdb_candidate.tmdb_id, seasons),
        )
        if validation["status"] == "passed":
            return local_confidence, validation
        validation["downgraded_from"] = local_confidence.value
        validation["downgraded_to"] = ConfidenceLevel.LOW.value
        return ConfidenceLevel.LOW, validation

    def _tv_season_years(self, tmdb_id: int, seasons: Sequence[int]) -> dict[int, int]:
        if not hasattr(self.tmdb, "get_tv_season_years"):
            return {}
        return self.tmdb.get_tv_season_years(tmdb_id, seasons, self.languages)

    def _extract_hint(
        self,
        candidate: MediaCandidate,
        *,
        prefetched_llm_hints: dict[str, MatchHint] | None = None,
        llm_attempted_ids: set[str] | None = None,
    ) -> tuple[MatchHint, list[MatchEvidence], str]:
        source_hint = self._source_hint(candidate)
        evidence = [hint_evidence("source_hint", source_hint)]
        if source_hint.context and source_hint.context.tv:
            evidence.append(match_context_evidence(source_hint.context, source_display_name=candidate.display_name))
        if source_hint.tmdb_id:
            return source_hint, evidence, "source_hint"
        if prefetched_llm_hints is not None and candidate.id in (llm_attempted_ids or set()):
            llm_hint = prefetched_llm_hints.get(candidate.id, MatchHint())
            evidence.append(hint_evidence("llm_hint", llm_hint))
            if llm_hint.has_identity:
                return merge_hints(source_hint, llm_hint), evidence, "llm_hint"
            return source_hint, evidence, "source_hint"
        llm_hint = self.llm_extractor.extract_hint(candidate)
        evidence.append(hint_evidence("llm_hint", llm_hint))
        if llm_hint.has_identity:
            return merge_hints(source_hint, llm_hint), evidence, "llm_hint"
        return source_hint, evidence, "source_hint"

    def _batch_llm_hints(
        self,
        candidates: Sequence[MediaCandidate],
        *,
        batch_size: int,
    ) -> tuple[dict[str, MatchHint], set[str]]:
        candidates_for_llm = [
            candidate
            for candidate in candidates
            if not self._source_hint(candidate).tmdb_id
        ]
        attempted_ids = {candidate.id for candidate in candidates_for_llm}
        if not candidates_for_llm:
            return {}, attempted_ids
        hints = self.llm_extractor.extract_hints(candidates_for_llm, batch_size=batch_size)
        return hints, attempted_ids

    def _source_hint(self, candidate: MediaCandidate) -> MatchHint:
        if self.media_name_extractor:
            hint = self.media_name_extractor.extract(candidate)
            if hint.has_identity:
                return hint
        return MatchHint(
            titles=(TitleHint(candidate.display_name, TitleKind.SOURCE, HintSource.DETERMINISTIC),)
        )

    def _result(
        self,
        source_candidate: MediaCandidate,
        tmdb_candidate: TMDBCandidate,
        confidence: ConfidenceLevel,
        evidence: list[MatchEvidence],
    ) -> MatchResult:
        return MatchResult(
            candidate_id=source_candidate.id,
            media_type=source_candidate.media_type,
            confidence=confidence,
            title=tmdb_candidate.title,
            original_title=tmdb_candidate.original_title,
            year=tmdb_candidate.year,
            tmdb_id=tmdb_candidate.tmdb_id,
            selected_external_id=f"tmdb:{tmdb_candidate.tmdb_id}",
            evidence=evidence,
            metadata=tmdb_candidate.metadata,
        )


def _batch_worker_count(candidate_count: int, requested: int | None) -> int:
    if candidate_count <= 1:
        return 1
    if requested is None:
        return min(8, candidate_count)
    return max(1, min(candidate_count, int(requested)))


