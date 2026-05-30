from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.domain.match import ConfidenceLevel
from app.domain.match import MatchResult, TMDBCandidate
from app.domain.media import MediaType
from app.services.identify.evidence import match_evidence_from_payload, match_evidence_payload


@dataclass
class CandidateMatch:
    source_candidate_id: str
    confidence: ConfidenceLevel
    metadata: dict[str, Any] | None = None
    metadata_source: str | None = None
    manual_override_tmdb_id: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


def candidate_match_from_result(source_candidate_id: str, match_result: MatchResult) -> CandidateMatch:
    metadata = metadata_from_match_result(match_result)
    return CandidateMatch(
        source_candidate_id=source_candidate_id,
        confidence=match_result.confidence,
        metadata=metadata or None,
        metadata_source="auto" if metadata else None,
        evidence=match_evidence_payload(match_result.evidence),
    )


def match_result_from_candidate(
    match: CandidateMatch,
    *,
    media_type: MediaType,
) -> MatchResult:
    metadata = match.metadata or {}
    return MatchResult(
        candidate_id=match.source_candidate_id,
        media_type=media_type,
        confidence=match.confidence,
        title=string_value(metadata.get("title") or metadata.get("name")),
        original_title=string_value(metadata.get("original_title")),
        year=optional_int(metadata.get("release_year") or metadata.get("year")),
        tmdb_id=optional_int(metadata.get("tmdb_id")),
        selected_external_id=string_value(metadata.get("selected_external_id")),
        evidence=match_evidence_from_payload(match.evidence, fallback_confidence=match.confidence),
        metadata=dict(metadata),
    )


def string_value(value: object) -> str | None:
    return str(value) if value is not None and str(value) else None


def optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def metadata_from_tmdb_candidate(candidate: TMDBCandidate) -> dict:
    value = dict(candidate.metadata)
    value.setdefault("media_type", candidate.media_type.value)
    value.setdefault("title", candidate.title)
    value.setdefault("original_title", candidate.original_title)
    value.setdefault("year", candidate.year)
    value.setdefault("release_year", candidate.year)
    value.setdefault("tmdb_id", candidate.tmdb_id)
    value.setdefault("selected_external_id", f"tmdb:{candidate.tmdb_id}")
    return _compact_metadata(value)


def metadata_from_match_result(match_result: MatchResult) -> dict:
    if not match_result.tmdb_id and not match_result.title:
        return {}
    value = dict(match_result.metadata)
    value.setdefault("media_type", match_result.media_type.value)
    value.setdefault("title", match_result.title)
    value.setdefault("original_title", match_result.original_title)
    value.setdefault("year", match_result.year)
    value.setdefault("release_year", match_result.year)
    value.setdefault("tmdb_id", match_result.tmdb_id)
    value.setdefault("selected_external_id", match_result.selected_external_id)
    return _compact_metadata(value)


def _compact_metadata(value: Mapping[str, object]) -> dict:
    return {key: item for key, item in value.items() if item is not None}
