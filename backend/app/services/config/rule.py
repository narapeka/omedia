from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.core.error import ConfigurationError
from app.domain.rule import OrganizeRule, TransferRule
from app.engines.name.depot import join_relative_fragments, split_depot_relative_path
from app.engines.rule.references import bundled_rule_references
from app.engines.rule.organize import OrganizeRuleContext, OrganizeRuleEngine
from app.engines.rule.transfer import TransferRuleContext, TransferRuleEngine


@dataclass(frozen=True)
class TransferPreviewPath:
    transfer_bucket: str
    organize_prefix: str
    media_relative_path: str
    destination_relative_path: str
    path_split_confidence: str


class RuleBook:
    """Owns rule validation, persistence, and preview calls."""

    def __init__(
        self,
        *,
        store=None,
        organize_engine: OrganizeRuleEngine | None = None,
        transfer_engine: TransferRuleEngine | None = None,
    ) -> None:
        self.store = store
        self.organize_engine = organize_engine or OrganizeRuleEngine()
        self.transfer_engine = transfer_engine or TransferRuleEngine()

    def list_organize(self) -> list[OrganizeRule]:
        return self.store.list_organize_rules()

    def references(self) -> dict[str, Any]:
        return bundled_rule_references()

    def save_organize(self, rule: OrganizeRule) -> OrganizeRule:
        rule = replace(rule, name=_clean_name(rule.name, "Organize rule"))
        _ensure_unique_name(rule.name, [item for item in self.store.list_organize_rules() if item.id != rule.id], "Organize rule")
        self.organize_engine.validate(rule)
        self.store.save_organize_rule(rule)
        return rule

    def delete_organize(self, rule_id: str) -> bool:
        rule = self.store.get_organize_rule(rule_id)
        rule_label = rule.name if rule else rule_id
        used_by = [
            origin.name
            for origin in self.store.list_origins()
            if origin.policy.organize_rule_id == rule_id
        ]
        if used_by:
            raise ConfigurationError(
                f"Organize rule {rule_label} is still used by Origin(s): {', '.join(sorted(used_by))}",
                code="rule.used",
                details={"rule_kind": "organize", "rule_id": rule_id, "rule_name": rule_label, "object": "Origin", "names": sorted(used_by), "count": len(used_by)},
            )
        return self.store.delete_organize_rule(rule_id)

    def preview_organize(
        self,
        rule: OrganizeRule,
        *,
        tmdb: dict[str, Any],
        relative_path: Path | str,
    ):
        return self.organize_engine.match(
            rule,
            OrganizeRuleContext(tmdb=tmdb, relative_path=relative_path),
        )

    def list_transfer(self) -> list[TransferRule]:
        return self.store.list_transfer_rules()

    def save_transfer(self, rule: TransferRule) -> TransferRule:
        rule = replace(rule, name=_clean_name(rule.name, "Transfer rule"))
        _ensure_unique_name(rule.name, [item for item in self.store.list_transfer_rules() if item.id != rule.id], "Transfer rule")
        self.transfer_engine.validate(rule)
        self.store.save_transfer_rule(rule)
        return rule

    def delete_transfer(self, rule_id: str) -> bool:
        rule = self.store.get_transfer_rule(rule_id)
        rule_label = rule.name if rule else rule_id
        used_by = [
            depot.name
            for depot in self.store.list_depots()
            if depot.policy.transfer_rule_id == rule_id
        ]
        if used_by:
            raise ConfigurationError(
                f"Transfer rule {rule_label} is still used by Depot(s): {', '.join(sorted(used_by))}",
                code="rule.used",
                details={"rule_kind": "transfer", "rule_id": rule_id, "rule_name": rule_label, "object": "Depot", "names": sorted(used_by), "count": len(used_by)},
            )
        return self.store.delete_transfer_rule(rule_id)

    def preview_transfer(self, rule: TransferRule, *, relative_path: Path | str):
        return self.transfer_engine.match(rule, TransferRuleContext(relative_path))

    def preview_transfer_path(self, rule: TransferRule, *, relative_path: Path | str) -> tuple[object, TransferPreviewPath]:
        result = self.preview_transfer(rule, relative_path=relative_path)
        split = split_depot_relative_path(relative_path)
        destination_relative_path = join_relative_fragments(
            split.organize_prefix,
            result.bucket,
            split.media_relative_path,
        )
        return result, TransferPreviewPath(
            transfer_bucket=result.bucket,
            organize_prefix=split.organize_prefix.as_posix() if split.organize_prefix.parts else "",
            media_relative_path=split.media_relative_path.as_posix(),
            destination_relative_path=destination_relative_path.as_posix(),
            path_split_confidence=split.confidence,
        )


def _clean_name(value: str, object_type: str) -> str:
    name = (value or "").strip()
    if not name:
        raise ConfigurationError(f"{object_type} name is required", code="name.required", details={"object": object_type})
    return name


def _ensure_unique_name(name: str, existing: list[OrganizeRule] | list[TransferRule], object_type: str) -> None:
    normalized = name.casefold()
    if any(item.name.strip().casefold() == normalized for item in existing):
        raise ConfigurationError(
            f"{object_type} name already exists: {name}",
            code="name.duplicate",
            details={"object": object_type, "name": name},
        )

