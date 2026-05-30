from __future__ import annotations

from pathlib import Path
from typing import Any

RULE_CONTEXT_KEYS = {"organize_rule_id", "transfer_rule_id", "matched_category", "bucket", "transfer_bucket"}
METADATA_CONTEXT_KEYS = {
    "metadata_tmdb_id",
    "metadata_title",
    "metadata_year",
    "metadata_source",
    "manual_override_tmdb_id",
    "media_type",
    "evidence_summary",
}


def replacement_provenance(
    *,
    source_path: Path,
    destination_path: Path,
    rule_context: dict[str, Any] | None = None,
    metadata_context: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provenance = dict(context or {})
    incoming_size = _safe_size(source_path)
    overwritten_size = _safe_size(destination_path)
    if incoming_size is not None:
        provenance.setdefault("incoming_size", incoming_size)
    if overwritten_size is not None:
        provenance.setdefault("overwritten_size", overwritten_size)
    if rule_context:
        rule = compact_context(rule_context)
        for key in RULE_CONTEXT_KEYS:
            if key in rule:
                provenance.setdefault(key, rule[key])
        provenance["rule_context"] = rule
    if metadata_context:
        metadata = compact_context(metadata_context)
        for key in METADATA_CONTEXT_KEYS:
            if key in metadata:
                provenance.setdefault(key, metadata[key])
        provenance["metadata_context"] = metadata
    return compact_context(provenance)


def compact_context(context: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in context.items() if value is not None}


def _safe_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None
