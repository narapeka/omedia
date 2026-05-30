from __future__ import annotations

from typing import Any

from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.models.base import Base, dump_json, load_json
from app.domain.rule import OrganizeRule, RuleCondition, RuleOperator, RuleCategory, TransferRule


class OrganizeRuleModel(Base):
    __tablename__ = "organize_rules"
    __table_args__ = (Index("idx_organize_rules_name", "name"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    categories_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    fallback_bucket: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str | None] = mapped_column(Text)

    @classmethod
    def from_domain(cls, rule: OrganizeRule) -> "OrganizeRuleModel":
        return cls(
            id=rule.id,
            name=rule.name,
            categories_json=dump_json(rule.categories),
            fallback_bucket=rule.fallback_bucket,
            description=rule.description,
        )

    def to_domain(self) -> OrganizeRule:
        return OrganizeRule(
            id=self.id,
            name=self.name,
            categories=_categories_from_json(self.categories_json),
            fallback_bucket=self.fallback_bucket,
            description=self.description,
        )


class TransferRuleModel(Base):
    __tablename__ = "transfer_rules"
    __table_args__ = (Index("idx_transfer_rules_name", "name"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    categories_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    fallback_bucket: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str | None] = mapped_column(Text)

    @classmethod
    def from_domain(cls, rule: TransferRule) -> "TransferRuleModel":
        return cls(
            id=rule.id,
            name=rule.name,
            categories_json=dump_json(rule.categories),
            fallback_bucket=rule.fallback_bucket,
            description=rule.description,
        )

    def to_domain(self) -> TransferRule:
        return TransferRule(
            id=self.id,
            name=self.name,
            categories=_categories_from_json(self.categories_json),
            fallback_bucket=self.fallback_bucket,
            description=self.description,
        )


def _categories_from_json(value: str | None) -> list[RuleCategory]:
    raw_categories = load_json(value) or []
    return [_category_from_mapping(category) for category in raw_categories]


def _category_from_mapping(value: dict[str, Any]) -> RuleCategory:
    raw_conditions = value.get("conditions") or []
    return RuleCategory(
        name=str(value.get("name") or ""),
        bucket=str(value.get("bucket") or ""),
        conditions=[
            RuleCondition(
                field=str(condition.get("field") or ""),
                op=RuleOperator(condition.get("op")),
                value=condition.get("value"),
            )
            for condition in raw_conditions
        ],
    )
