from __future__ import annotations

from pathlib import Path
from typing import Any

from app.domain.activity import ActivityArea, ActivityEntityType
from app.engines.activity.provenance import compact_context

SECRET_CONTEXT_KEYS = ("api_key", "authorization", "password", "secret", "prompt", "raw_response", "headers")
SECRET_TOKEN_KEYS = {"token", "access_token", "refresh_token", "auth_token", "bearer_token"}


def curated(context: dict[str, Any]) -> dict[str, Any]:
    return compact_context({
        key: value
        for key, value in context.items()
        if not is_secret_key(key)
    })


def is_secret_key(key: str) -> bool:
    normalized = key.casefold()
    return normalized in SECRET_TOKEN_KEYS or any(secret in normalized for secret in SECRET_CONTEXT_KEYS)


def reason(context: dict[str, Any]) -> str | None:
    for key in ("reason", "error_code", "error_type", "blocked_reason", "skip_reason"):
        value = context.get(key)
        if value:
            return str(value)
    return None


def text(value: Any) -> str | None:
    return str(value) if value is not None and str(value) else None


def entity_text(value: str | Path | None) -> str | None:
    return str(value) if value is not None and str(value) else None


def entity_type(
    source_path: Path | None,
    destination_path: Path | None,
    context: dict[str, Any] | None,
) -> ActivityEntityType:
    value = (context or {}).get("entity_type")
    if value:
        return ActivityEntityType(str(value))
    scope = str((context or {}).get("scope") or (context or {}).get("depot_scope") or "")
    kind = str((context or {}).get("depot_candidate_kind") or "")
    if scope == "candidate" and kind == "folder":
        return ActivityEntityType.FOLDER
    path = source_path or destination_path
    if path is not None:
        try:
            if path.exists() and path.is_dir():
                return ActivityEntityType.FOLDER
        except OSError:
            pass
        if not path.suffix and scope == "candidate":
            return ActivityEntityType.FOLDER
    return ActivityEntityType.FILE


def session_source(origin: "Origin | None", depot: "Depot | None", context: dict[str, Any] | None) -> str | None:
    if origin:
        return origin.name or origin.id
    if depot:
        return depot.name or depot.id
    context = context or {}
    return text(context.get("origin_name") or context.get("origin_id") or context.get("media_type"))


def session_target(depot: "Depot | None", context: dict[str, Any] | None) -> str | None:
    if depot:
        return depot.name or depot.id
    context = context or {}
    return text(context.get("depot_name") or context.get("depot_id") or context.get("target_library_path") or context.get("library_path"))


def origin_id(origin: "Origin | None", context: dict[str, Any]) -> str | None:
    return origin.id if origin else text(context.get("origin_id"))


def origin_name(origin: "Origin | None", context: dict[str, Any]) -> str | None:
    return origin.name if origin and origin.name else text(context.get("origin_name"))


def origin_path(origin: "Origin | None", context: dict[str, Any]) -> Path | None:
    if origin:
        return origin.path
    value = context.get("origin_path")
    return Path(str(value)) if value else None


def depot_id(depot: "Depot | None", context: dict[str, Any]) -> str | None:
    return depot.id if depot else text(context.get("depot_id"))


def depot_name(depot: "Depot | None", context: dict[str, Any]) -> str | None:
    return depot.name if depot and depot.name else text(context.get("depot_name"))


def depot_path(depot: "Depot | None", context: dict[str, Any]) -> Path | None:
    if depot:
        return depot.path
    value = context.get("depot_path")
    return Path(str(value)) if value else None


def library_path(depot: "Depot | None", context: dict[str, Any]) -> Path | None:
    if depot:
        return depot.policy.target_library_path
    value = context.get("library_path") or context.get("target_library_path")
    return Path(str(value)) if value else None


def rule_id(rule: "OrganizeRule | TransferRule | None", context: dict[str, Any]) -> str | None:
    return rule.id if rule else text(context.get("rule_id") or context.get("organize_rule_id") or context.get("transfer_rule_id"))


def rule_name(rule: "OrganizeRule | TransferRule | None", context: dict[str, Any]) -> str | None:
    return rule.name if rule else text(context.get("rule_name"))


def media_type(origin: "Origin | None", depot: "Depot | None", context: dict[str, Any]) -> str | None:
    if depot:
        return depot.media_type.value
    if origin:
        return origin.media_type.value
    return text(context.get("media_type") or context.get("media_kind"))


def tmdb_id(context: dict[str, Any]) -> str | None:
    value = context.get("tmdb_id") or context.get("metadata_tmdb_id") or context.get("manual_override_tmdb_id")
    return text(value)


def transfer_area(requested_by: str | None) -> ActivityArea:
    return ActivityArea.SCHEDULED_TRANSFER if requested_by == "schedule" else ActivityArea.MANUAL_TRANSFER
