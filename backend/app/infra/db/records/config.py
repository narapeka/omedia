from __future__ import annotations

from sqlalchemy import select

from app.infra.db.models.depot import DepotModel
from app.infra.db.models.origin import OriginModel
from app.infra.db.models.watch import WatchSettingModel
from app.domain.origin import OriginTrigger
from app.domain.origin import Origin
from app.domain.depot import Depot
from app.domain.watch import WatchSettings


class ConfigRecords:
    def save_watch_settings(self, config: WatchSettings) -> None:
        with self.session_scope() as session:
            session.merge(WatchSettingModel.from_domain(config))

    def replace_watch_root(self, config: WatchSettings) -> None:
        with self.session_scope() as session:
            session.query(OriginModel).filter(
                OriginModel.trigger == OriginTrigger.WATCH.value
            ).delete(synchronize_session=False)
            session.merge(WatchSettingModel.from_domain(config))

    def get_watch_settings(self) -> WatchSettings | None:
        with self.session_factory() as session:
            model = session.get(WatchSettingModel, "main")
            return model.to_domain() if model else None

    def save_origin(self, origin: Origin) -> None:
        with self.session_scope() as session:
            session.merge(OriginModel.from_domain(origin))

    def get_origin(self, origin_id: str) -> Origin | None:
        with self.session_factory() as session:
            model = session.get(OriginModel, origin_id)
            return model.to_domain() if model else None

    def list_origins(self) -> list[Origin]:
        stmt = select(OriginModel).order_by(OriginModel.id)
        with self.session_factory() as session:
            return [model.to_domain() for model in session.scalars(stmt).all()]

    def delete_origin(self, origin_id: str) -> bool:
        with self.session_scope() as session:
            model = session.get(OriginModel, origin_id)
            if model is None:
                return False
            session.delete(model)
            return True

    def save_depot(self, depot: Depot) -> None:
        with self.session_scope() as session:
            session.merge(DepotModel.from_domain(depot))

    def get_depot(self, depot_id: str) -> Depot | None:
        with self.session_factory() as session:
            model = session.get(DepotModel, depot_id)
            return model.to_domain() if model else None

    def list_depots(self) -> list[Depot]:
        stmt = select(DepotModel).order_by(DepotModel.id)
        with self.session_factory() as session:
            return [model.to_domain() for model in session.scalars(stmt).all()]

    def delete_depot(self, depot_id: str) -> bool:
        with self.session_scope() as session:
            model = session.get(DepotModel, depot_id)
            if model is None:
                return False
            session.delete(model)
            return True
