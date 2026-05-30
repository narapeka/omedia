from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from app.domain.match import ConfidenceLevel, MatchEvidence


MATCH_EVIDENCE_SUMMARY_KEY = "summary"


@dataclass(frozen=True)
class MatchEvidenceSummary:
    source: str | None
    confidence: str | None
    values: dict[str, Any]
    reason: str | None = None

    @classmethod
    def from_evidence(cls, evidence: MatchEvidence) -> "MatchEvidenceSummary":
        return cls(
            source=evidence.source,
            confidence=evidence.confidence.value,
            values=dict(evidence.values),
            reason=evidence.reason,
        )

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "MatchEvidenceSummary":
        values = payload.get("values")
        return cls(
            source=_string_value(payload.get("source")),
            confidence=_string_value(payload.get("confidence")),
            values=dict(values) if isinstance(values, Mapping) else {},
            reason=_string_value(payload.get("reason")),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "confidence": self.confidence,
            "values": dict(self.values),
            "reason": self.reason,
        }

    def as_evidence(self, *, fallback_confidence: ConfidenceLevel) -> MatchEvidence:
        try:
            confidence = ConfidenceLevel(self.confidence) if self.confidence else fallback_confidence
        except ValueError:
            confidence = fallback_confidence
        return MatchEvidence(
            source=self.source or "candidate_match",
            confidence=confidence,
            values=dict(self.values),
            reason=self.reason,
        )


def match_evidence_payload(evidence: Iterable[MatchEvidence]) -> dict[str, list[dict[str, Any]]]:
    return {MATCH_EVIDENCE_SUMMARY_KEY: [MatchEvidenceSummary.from_evidence(item).as_dict() for item in evidence]}


def match_evidence_summary(evidence: MatchEvidence) -> dict[str, Any]:
    return MatchEvidenceSummary.from_evidence(evidence).as_dict()


def match_evidence_summary_payload(evidence: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    summaries = match_evidence_summaries(evidence)
    if summaries is None:
        return None
    return [summary.as_dict() for summary in summaries]


def match_evidence_view_payload(evidence: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(evidence)
    summaries = match_evidence_summary_payload(evidence)
    if summaries is not None:
        payload[MATCH_EVIDENCE_SUMMARY_KEY] = summaries
    return payload


def match_evidence_summaries(evidence: Mapping[str, Any]) -> list[MatchEvidenceSummary] | None:
    summary = evidence.get(MATCH_EVIDENCE_SUMMARY_KEY)
    if not isinstance(summary, list):
        return None
    return [MatchEvidenceSummary.from_payload(item) for item in summary if isinstance(item, Mapping)]


def match_evidence_from_payload(
    evidence: Mapping[str, Any],
    *,
    fallback_confidence: ConfidenceLevel,
) -> list[MatchEvidence]:
    summaries = match_evidence_summaries(evidence)
    if summaries is None:
        return []
    return [summary.as_evidence(fallback_confidence=fallback_confidence) for summary in summaries]


def _string_value(value: object) -> str | None:
    return str(value) if value is not None and str(value) else None
