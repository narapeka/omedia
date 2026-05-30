from __future__ import annotations

from typing import Callable, Sequence

from app.domain.match import TMDBCandidate, TVYearFact, TVYearScope

SeasonYearLookup = Callable[[Sequence[int]], dict[int, int]]


def validate_year_facts(
    tmdb_candidate: TMDBCandidate,
    facts: Sequence[TVYearFact],
    *,
    season_year_lookup: SeasonYearLookup,
) -> dict[str, object]:
    tolerance = 1
    fact_results: list[dict[str, object]] = []
    pending_season_indexes: list[int] = []
    for fact in facts:
        result: dict[str, object] = {
            **fact.evidence_values(),
            "status": "pending",
            "show_year_validation": _show_year_validation(fact.year, tmdb_candidate.year, tolerance),
        }
        if fact.scope == TVYearScope.SHOW_YEAR:
            result["status"] = result["show_year_validation"]["status"]
        elif fact.scope == TVYearScope.SHOW_OR_SEASON_YEAR and result["show_year_validation"]["status"] == "passed":
            result["status"] = "passed"
            result["matched_by"] = "show_year"
        elif fact.season is None:
            result["status"] = "unavailable"
            result["reason"] = "missing_season"
        else:
            pending_season_indexes.append(len(fact_results))
        fact_results.append(result)

    season_years: dict[int, int] = {}
    if pending_season_indexes:
        seasons = [
            int(facts[index].season)
            for index in pending_season_indexes
            if facts[index].season is not None
        ]
        season_years = season_year_lookup(seasons)

    for index in pending_season_indexes:
        fact = facts[index]
        result = fact_results[index]
        season = fact.season
        season_year = season_years.get(int(season)) if season is not None else None
        season_validation = _season_year_validation(fact.year, season, season_year, tolerance)
        result["season_year_validation"] = season_validation
        if season_validation["status"] == "passed":
            result["status"] = "passed"
            result["matched_by"] = "season_year"
        else:
            result["status"] = season_validation["status"]
            result["reason"] = "required_season_year_" + season_validation["status"]

    failed = [item for item in fact_results if item.get("status") != "passed"]
    scopes = {fact.scope for fact in facts}
    return {
        "status": "passed" if not failed else "failed",
        "tolerance": tolerance,
        "final_year_policy": _final_year_policy(scopes),
        "season_year_lookup_requested": sorted(
            {int(facts[index].season) for index in pending_season_indexes if facts[index].season is not None}
        ),
        "season_year_lookup_result": season_years,
        "facts": fact_results,
        "failed_facts": failed,
    }


def _show_year_validation(requested_year: int, tmdb_show_year: int | None, tolerance: int) -> dict[str, object]:
    status = "unavailable"
    if tmdb_show_year is not None:
        status = "passed" if _years_match(requested_year, tmdb_show_year, tolerance) else "mismatch"
    return {
        "requested_year": requested_year,
        "tmdb_show_year": tmdb_show_year,
        "tolerance": tolerance,
        "status": status,
    }


def _season_year_validation(
    requested_year: int,
    season: int | None,
    tmdb_season_year: int | None,
    tolerance: int,
) -> dict[str, object]:
    status = "unavailable"
    if tmdb_season_year is not None:
        status = "passed" if _years_match(requested_year, tmdb_season_year, tolerance) else "mismatch"
    return {
        "requested_year": requested_year,
        "season": season,
        "tmdb_season_year": tmdb_season_year,
        "tolerance": tolerance,
        "status": status,
    }


def _final_year_policy(scopes: set[TVYearScope]) -> str:
    if len(scopes) > 1:
        return "mixed_scoped_years"
    return next(iter(scopes)).value if scopes else "none"


def _years_match(left: int, right: int, tolerance: int) -> bool:
    return abs(int(left) - int(right)) <= tolerance
