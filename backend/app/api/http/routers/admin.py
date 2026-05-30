from __future__ import annotations

import yaml
from fastapi import APIRouter, Response
from pydantic import ValidationError

from app.api.http.deps import Admin
from app.api.http.schemas.admin import (
    AdminActivityPruneResult,
    AdminBackup,
    AdminClearedCounts,
    AdminPruneRequest,
    AdminRecordCounts,
    AdminRestoreRequest,
    AdminRestoreResult,
    AdminTmdbClearResult,
    AdminTransferPruneResult,
)
from app.api.http.schemas.common import DEFAULT_API_RESPONSES
from app.core.error import ConfigurationError

router = APIRouter(prefix="/admin", tags=["admin"], responses=DEFAULT_API_RESPONSES)

BACKUP_FILENAME = "omedia-config-backup.yaml"


@router.post("/cache/tmdb/clear", response_model=AdminTmdbClearResult)
def clear_admin_tmdb_cache(admin: Admin) -> AdminTmdbClearResult:
    return AdminTmdbClearResult(deleted_entries=admin.clear_tmdb_cache())


@router.post("/activity/prune", response_model=AdminActivityPruneResult)
def prune_admin_activity(
    admin: Admin,
    payload: AdminPruneRequest | None = None,
) -> AdminActivityPruneResult:
    request = payload or AdminPruneRequest()
    cutoff, deleted = admin.prune_activity(request.older_than_days)
    return AdminActivityPruneResult(
        older_than_days=request.older_than_days,
        cutoff=cutoff,
        deleted_events=deleted,
    )


@router.post("/transfer/prune", response_model=AdminTransferPruneResult)
def prune_admin_transfer(
    admin: Admin,
    payload: AdminPruneRequest | None = None,
) -> AdminTransferPruneResult:
    request = payload or AdminPruneRequest()
    cutoff, counts = admin.prune_transfer(request.older_than_days)
    return AdminTransferPruneResult(
        older_than_days=request.older_than_days,
        cutoff=cutoff,
        deleted_jobs=counts.deleted_jobs,
    )


@router.get(
    "/backup",
    response_class=Response,
    responses={
        200: {
            "description": "Admin backup YAML.",
            "content": {
                "application/x-yaml": {
                    "schema": {"type": "string", "title": "AdminBackupYaml"},
                }
            },
        }
    },
)
def backup_admin(admin: Admin) -> Response:
    backup = AdminBackup.model_validate(admin.backup_config())
    content = yaml.safe_dump(backup.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
    return Response(
        content=content,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{BACKUP_FILENAME}"'},
    )


@router.post("/restore", response_model=AdminRestoreResult)
def restore_admin(
    payload: AdminRestoreRequest,
    admin: Admin,
) -> AdminRestoreResult:
    data = _parse_config_backup(payload.content)
    try:
        backup = AdminBackup.model_validate(data)
    except ValidationError as exc:
        raise ConfigurationError(str(exc)) from exc
    result = admin.restore_config(backup.model_dump(mode="python"))
    return AdminRestoreResult(
        restored=AdminRecordCounts(
            watch_settings=result.restored.watch_settings,
            origins=result.restored.origins,
            depots=result.restored.depots,
            organize_rules=result.restored.organize_rules,
            transfer_rules=result.restored.transfer_rules,
        ),
        cleared=AdminClearedCounts(
            activity_events=result.cleared.activity_events,
            transfer_jobs=result.cleared.transfer_jobs,
            tmdb_detail_cache=result.cleared.tmdb_detail_cache,
        ),
    )


def _parse_config_backup(content: str):
    try:
        data = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid backup YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError("Backup YAML root must be an object")
    return data
