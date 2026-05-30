from __future__ import annotations

from pathlib import Path

from sqlalchemy import Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.models.base import Base, dump_json, format_dt, load_json, parse_dt
from app.domain.activity import ActivityAction, ActivityArea, ActivityEntityType, ActivityEvent, ActivityStatus


class ActivityEventModel(Base):
    __tablename__ = "activity_events"
    __table_args__ = (
        Index("idx_activity_events_time", "time"),
        Index("idx_activity_events_area", "area"),
        Index("idx_activity_events_entity_type", "entity_type"),
        Index("idx_activity_events_action", "action"),
        Index("idx_activity_events_status", "status"),
        Index("idx_activity_events_reason", "reason"),
        Index("idx_activity_events_trace_id", "trace_id"),
        Index("idx_activity_events_origin_id", "origin_id"),
        Index("idx_activity_events_depot_id", "depot_id"),
        Index("idx_activity_events_media_type", "media_type"),
        Index("idx_activity_events_tmdb_id", "tmdb_id"),
        Index("idx_activity_events_entity_source", "entity_source"),
        Index("idx_activity_events_entity_target", "entity_target"),
        Index("idx_activity_events_library_path", "library_path"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    time: Mapped[str] = mapped_column(Text, nullable=False)
    area: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    trace_id: Mapped[str | None] = mapped_column(Text)
    entity_source: Mapped[str | None] = mapped_column(Text)
    entity_target: Mapped[str | None] = mapped_column(Text)
    media_type: Mapped[str | None] = mapped_column(Text)
    tmdb_id: Mapped[str | None] = mapped_column(Text)
    origin_id: Mapped[str | None] = mapped_column(Text)
    origin_name: Mapped[str | None] = mapped_column(Text)
    origin_path: Mapped[str | None] = mapped_column(Text)
    depot_id: Mapped[str | None] = mapped_column(Text)
    depot_name: Mapped[str | None] = mapped_column(Text)
    depot_path: Mapped[str | None] = mapped_column(Text)
    library_path: Mapped[str | None] = mapped_column(Text)
    rule_id: Mapped[str | None] = mapped_column(Text)
    rule_name: Mapped[str | None] = mapped_column(Text)
    context_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    @classmethod
    def from_domain(cls, event: ActivityEvent) -> "ActivityEventModel":
        return cls(
            id=event.id,
            time=format_dt(event.time),
            area=event.area.value,
            action=event.action.value,
            status=event.status.value,
            reason=event.reason,
            summary=event.summary,
            entity_type=event.entity_type.value,
            trace_id=event.trace_id,
            entity_source=event.entity_source,
            entity_target=event.entity_target,
            media_type=event.media_type,
            tmdb_id=str(event.tmdb_id) if event.tmdb_id is not None else None,
            origin_id=event.origin_id,
            origin_name=event.origin_name,
            origin_path=str(event.origin_path) if event.origin_path else None,
            depot_id=event.depot_id,
            depot_name=event.depot_name,
            depot_path=str(event.depot_path) if event.depot_path else None,
            library_path=str(event.library_path) if event.library_path else None,
            rule_id=event.rule_id,
            rule_name=event.rule_name,
            context_json=dump_json(event.context),
        )

    def to_domain(self) -> ActivityEvent:
        return ActivityEvent(
            id=self.id,
            time=parse_dt(self.time),
            area=ActivityArea(self.area),
            action=ActivityAction(self.action),
            status=ActivityStatus(self.status),
            reason=self.reason,
            summary=self.summary,
            entity_type=ActivityEntityType(self.entity_type),
            trace_id=self.trace_id,
            entity_source=self.entity_source,
            entity_target=self.entity_target,
            media_type=self.media_type,
            tmdb_id=self.tmdb_id,
            origin_id=self.origin_id,
            origin_name=self.origin_name,
            origin_path=Path(self.origin_path) if self.origin_path else None,
            depot_id=self.depot_id,
            depot_name=self.depot_name,
            depot_path=Path(self.depot_path) if self.depot_path else None,
            library_path=Path(self.library_path) if self.library_path else None,
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            context=load_json(self.context_json) or {},
        )
