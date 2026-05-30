from __future__ import annotations

from pathlib import Path

from sqlalchemy import Boolean, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.media import MediaType
from app.domain.transfer import TransferTrigger
from app.domain.depot import ResolveMode, TransferPolicy, Depot
from app.infra.db.models.base import Base, dump_json, load_json


class DepotModel(Base):
    __tablename__ = "depots"
    __table_args__ = (
        Index("idx_depots_path", "path", unique=True),
        Index("idx_depots_name", "name"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    target_library_path: Mapped[str] = mapped_column(Text, nullable=False)
    transfer_trigger: Mapped[str] = mapped_column(Text, nullable=False)
    transfer_rule_id: Mapped[str | None] = mapped_column(Text)
    schedule: Mapped[str | None] = mapped_column(Text)
    resolve_mode: Mapped[str] = mapped_column(Text, nullable=False, default=ResolveMode.FULL.value)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    @classmethod
    def from_domain(cls, depot: Depot) -> "DepotModel":
        return cls(
            id=depot.id,
            name=depot.name,
            path=str(depot.path),
            media_type=depot.media_type.value,
            enabled=depot.enabled,
            target_library_path=str(depot.policy.target_library_path),
            transfer_trigger=depot.policy.trigger.value,
            transfer_rule_id=depot.policy.transfer_rule_id,
            schedule=depot.policy.schedule,
            resolve_mode=depot.resolve_mode.value,
            metadata_json=dump_json(depot.metadata),
        )

    def to_domain(self) -> Depot:
        return Depot(
            id=self.id,
            name=self.name,
            path=Path(self.path),
            media_type=MediaType(self.media_type),
            enabled=self.enabled,
            policy=TransferPolicy(
                target_library_path=Path(self.target_library_path),
                trigger=TransferTrigger(self.transfer_trigger),
                transfer_rule_id=self.transfer_rule_id,
                schedule=self.schedule,
            ),
            resolve_mode=ResolveMode(self.resolve_mode),
            metadata=load_json(self.metadata_json) or {},
        )
