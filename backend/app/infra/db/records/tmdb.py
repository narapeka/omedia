from __future__ import annotations

from app.infra.db.models.cache import TMDBDetailCacheModel
from app.domain.cache import TMDBDetailCache


class TMDBCacheRecords:
    def save_tmdb_detail(self, entry: TMDBDetailCache) -> None:
        with self.session_scope() as session:
            session.merge(TMDBDetailCacheModel.from_domain(entry))

    def get_tmdb_detail(self, media_type: str, tmdb_id: int) -> TMDBDetailCache | None:
        with self.session_factory() as session:
            model = session.get(TMDBDetailCacheModel, {"media_type": media_type, "tmdb_id": int(tmdb_id)})
            return model.to_domain() if model else None

    def delete_tmdb_detail(self, media_type: str, tmdb_id: int) -> bool:
        with self.session_scope() as session:
            model = session.get(TMDBDetailCacheModel, {"media_type": media_type, "tmdb_id": int(tmdb_id)})
            if model is None:
                return False
            session.delete(model)
            return True

    def clear_tmdb_details(self) -> int:
        with self.session_scope() as session:
            return session.query(TMDBDetailCacheModel).delete()
