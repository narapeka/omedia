from __future__ import annotations

from pathlib import Path

from sqlalchemy import Boolean, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.media import MediaType
from app.domain.origin import OriginTrigger
from app.domain.origin import OrganizePolicy, Origin
from app.infra.db.models.base import Base, dump_json, load_json


class OriginModel(Base):
    __tablename__ = "origins"
    __table_args__ = (
        Index("idx_origins_path", "path", unique=True),
        Index("idx_origins_name", "name"),
        Index("idx_origins_trigger", "trigger"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    target_depot_id: Mapped[str] = mapped_column(Text, nullable=False)
    organize_rule_id: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    @classmethod
    def from_domain(cls, origin: Origin) -> "OriginModel":
        return cls(
            id=origin.id,
            name=origin.name,
            path=str(origin.path),
            media_type=origin.media_type.value,
            trigger=origin.trigger.value,
            enabled=origin.enabled,
            target_depot_id=origin.policy.target_depot_id,
            organize_rule_id=origin.policy.organize_rule_id,
            metadata_json=dump_json(origin.metadata),
        )

    def to_domain(self) -> Origin:
        return Origin(
            id=self.id,
            name=self.name,
            path=Path(self.path),
            media_type=MediaType(self.media_type),
            trigger=OriginTrigger(self.trigger),
            enabled=self.enabled,
            policy=OrganizePolicy(
                target_depot_id=self.target_depot_id,
                organize_rule_id=self.organize_rule_id,
            ),
            metadata=load_json(self.metadata_json) or {},
        )
