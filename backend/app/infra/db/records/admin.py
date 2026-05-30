from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from app.infra.db.models.activity import ActivityEventModel
from app.infra.db.models.cache import TMDBDetailCacheModel
from app.infra.db.models.depot import DepotModel
from app.infra.db.models.origin import OriginModel
from app.infra.db.models.rule import OrganizeRuleModel, TransferRuleModel
from app.infra.db.models.transfer import TransferJobModel
from app.infra.db.models.watch import WatchSettingModel
from app.infra.db.models.base import parse_dt
from app.domain.transfer import TransferStatus
from app.domain.origin import Origin
from app.domain.depot import Depot
from app.domain.watch import WatchSettings
from app.domain.rule import OrganizeRule, TransferRule


TERMINAL_TRANSFER_STATUSES = {
    TransferStatus.SUCCEEDED.value,
    TransferStatus.SKIPPED.value,
    TransferStatus.FAILED.value,
    TransferStatus.CANCELLED.value,
}

@dataclass(frozen=True)
class AdminTransferPruneCounts:
    deleted_jobs: int = 0


@dataclass(frozen=True)
class AdminRestoreCounts:
    watch_settings: int = 0
    origins: int = 0
    depots: int = 0
    organize_rules: int = 0
    transfer_rules: int = 0


@dataclass(frozen=True)
class AdminClearedCounts:
    activity_events: int = 0
    transfer_jobs: int = 0
    tmdb_detail_cache: int = 0


@dataclass(frozen=True)
class AdminReplaceResult:
    restored: AdminRestoreCounts
    cleared: AdminClearedCounts


@dataclass(frozen=True)
class AdminBackupSnapshot:
    watch_settings: WatchSettings | None
    origins: list[Origin]
    depots: list[Depot]
    organize_rules: list[OrganizeRule]
    transfer_rules: list[TransferRule]


class AdminRecords:
    def count_activity_events_before(self, cutoff: datetime) -> int:
        with self.session_factory() as session:
            models = session.execute(select(ActivityEventModel.id, ActivityEventModel.time)).all()
            return sum(1 for _id, event_time in models if _is_before(event_time, cutoff))

    def delete_activity_events_before(self, cutoff: datetime) -> int:
        with self.session_scope() as session:
            models = session.scalars(select(ActivityEventModel)).all()
            ids = [model.id for model in models if _is_before(model.time, cutoff)]
            if not ids:
                return 0
            return session.query(ActivityEventModel).filter(ActivityEventModel.id.in_(ids)).delete(synchronize_session=False)

    def prune_transfer_history_before(self, cutoff: datetime) -> AdminTransferPruneCounts:
        with self.session_scope() as session:
            job_models = session.scalars(select(TransferJobModel)).all()
            job_ids = [
                model.id
                for model in job_models
                if model.status in TERMINAL_TRANSFER_STATUSES and _is_before(model.finished_at, cutoff)
            ]
            deleted_jobs = 0
            if job_ids:
                deleted_jobs = session.query(TransferJobModel).filter(TransferJobModel.id.in_(job_ids)).delete(synchronize_session=False)

            return AdminTransferPruneCounts(deleted_jobs=deleted_jobs)

    def export_admin_backup(self) -> AdminBackupSnapshot:
        return AdminBackupSnapshot(
            watch_settings=self.get_watch_settings(),
            origins=self.list_origins(),
            depots=self.list_depots(),
            organize_rules=self.list_organize_rules(),
            transfer_rules=self.list_transfer_rules(),
        )

    def replace_admin_backup(
        self,
        *,
        watch_settings: WatchSettings | None,
        origins: list[Origin],
        depots: list[Depot],
        organize_rules: list[OrganizeRule],
        transfer_rules: list[TransferRule],
    ) -> AdminReplaceResult:
        with self.session_scope() as session:
            cleared_activity = session.query(ActivityEventModel).delete()
            cleared_jobs = session.query(TransferJobModel).delete()
            cleared_cache = session.query(TMDBDetailCacheModel).delete()

            session.query(OriginModel).delete()
            session.query(DepotModel).delete()
            session.query(WatchSettingModel).delete()
            session.query(OrganizeRuleModel).delete()
            session.query(TransferRuleModel).delete()

            if watch_settings is not None:
                session.merge(WatchSettingModel.from_domain(watch_settings))
            for rule in organize_rules:
                session.merge(OrganizeRuleModel.from_domain(rule))
            for rule in transfer_rules:
                session.merge(TransferRuleModel.from_domain(rule))
            for origin in origins:
                session.merge(OriginModel.from_domain(origin))
            for depot in depots:
                session.merge(DepotModel.from_domain(depot))

            return AdminReplaceResult(
                restored=AdminRestoreCounts(
                    watch_settings=1 if watch_settings is not None else 0,
                    origins=len(origins),
                    depots=len(depots),
                    organize_rules=len(organize_rules),
                    transfer_rules=len(transfer_rules),
                ),
                cleared=AdminClearedCounts(
                    activity_events=cleared_activity,
                    transfer_jobs=cleared_jobs,
                    tmdb_detail_cache=cleared_cache,
                ),
            )


def _is_before(value: str | None, cutoff: datetime) -> bool:
    parsed = parse_dt(value)
    if parsed is None:
        return False
    if parsed.tzinfo is None and cutoff.tzinfo is not None:
        parsed = parsed.replace(tzinfo=cutoff.tzinfo)
    if parsed.tzinfo is not None and cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=parsed.tzinfo)
    return parsed < cutoff
