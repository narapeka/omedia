from __future__ import annotations

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.models.base import Base, dump_json, load_json, format_dt, parse_dt
from app.domain.cache import TMDBDetailCache


class TMDBDetailCacheModel(Base):
    __tablename__ = "tmdb_detail_cache"

    media_type: Mapped[str] = mapped_column(Text, primary_key=True)
    tmdb_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    fetched_at: Mapped[str] = mapped_column(Text, nullable=False)

    @classmethod
    def from_domain(cls, entry: TMDBDetailCache) -> "TMDBDetailCacheModel":
        return cls(
            media_type=entry.media_type,
            tmdb_id=entry.tmdb_id,
            metadata_json=dump_json(entry.metadata),
            fetched_at=format_dt(entry.fetched_at),
        )

    def to_domain(self) -> TMDBDetailCache:
        return TMDBDetailCache(
            media_type=self.media_type,
            tmdb_id=self.tmdb_id,
            metadata=load_json(self.metadata_json) or {},
            fetched_at=parse_dt(self.fetched_at),
        )
