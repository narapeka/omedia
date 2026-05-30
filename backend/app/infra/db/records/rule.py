from __future__ import annotations

from sqlalchemy import select

from app.infra.db.models.rule import OrganizeRuleModel, TransferRuleModel
from app.domain.rule import OrganizeRule, TransferRule


class RuleRecords:
    def save_organize_rule(self, rule: OrganizeRule) -> None:
        with self.session_scope() as session:
            session.merge(OrganizeRuleModel.from_domain(rule))

    def get_organize_rule(self, rule_id: str) -> OrganizeRule | None:
        with self.session_factory() as session:
            model = session.get(OrganizeRuleModel, rule_id)
            return model.to_domain() if model else None

    def list_organize_rules(self) -> list[OrganizeRule]:
        stmt = select(OrganizeRuleModel).order_by(OrganizeRuleModel.id)
        with self.session_factory() as session:
            return [model.to_domain() for model in session.scalars(stmt).all()]

    def delete_organize_rule(self, rule_id: str) -> bool:
        with self.session_scope() as session:
            model = session.get(OrganizeRuleModel, rule_id)
            if model is None:
                return False
            session.delete(model)
            return True

    def save_transfer_rule(self, rule: TransferRule) -> None:
        with self.session_scope() as session:
            session.merge(TransferRuleModel.from_domain(rule))

    def get_transfer_rule(self, rule_id: str) -> TransferRule | None:
        with self.session_factory() as session:
            model = session.get(TransferRuleModel, rule_id)
            return model.to_domain() if model else None

    def list_transfer_rules(self) -> list[TransferRule]:
        stmt = select(TransferRuleModel).order_by(TransferRuleModel.id)
        with self.session_factory() as session:
            return [model.to_domain() for model in session.scalars(stmt).all()]

    def delete_transfer_rule(self, rule_id: str) -> bool:
        with self.session_scope() as session:
            model = session.get(TransferRuleModel, rule_id)
            if model is None:
                return False
            session.delete(model)
            return True
