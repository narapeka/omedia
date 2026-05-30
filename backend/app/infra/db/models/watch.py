from __future__ import annotations

from pathlib import Path

from sqlalchemy import Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.watch import WatchSettings
from app.infra.db.models.base import Base, dump_json, load_json


class WatchSettingModel(Base):
    __tablename__ = "watch_settings"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default="main")
    path: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    @classmethod
    def from_domain(cls, config: WatchSettings) -> "WatchSettingModel":
        return cls(
            id=config.id,
            path=str(config.path),
            enabled=config.enabled,
            metadata_json=dump_json(config.metadata),
        )

    def to_domain(self) -> WatchSettings:
        return WatchSettings(
            id=self.id,
            path=Path(self.path),
            enabled=self.enabled,
            metadata=load_json(self.metadata_json) or {},
        )
