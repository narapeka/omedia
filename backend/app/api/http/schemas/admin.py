from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import ConfigDict, Field

from app.api.http.schemas.common import ApiModel
from app.api.http.schemas.config import OrganizePolicy, OrganizeRule, OrganizeSettings, TransferRule, WatchRuntimeSettings
from app.api.http.schemas.transfer import TransferPolicy
from app.domain.depot import ResolveMode
from app.domain.media import MediaType
from app.domain.origin import OriginTrigger


class AdminPruneRequest(ApiModel):
    older_than_days: int = Field(default=180, gt=0)


class AdminTmdbClearResult(ApiModel):
    ok: bool = True
    deleted_entries: int


class AdminActivityPruneResult(ApiModel):
    ok: bool = True
    older_than_days: int
    cutoff: datetime
    deleted_events: int


class AdminTransferPruneResult(ApiModel):
    ok: bool = True
    older_than_days: int
    cutoff: datetime
    deleted_jobs: int


class AdminRecordCounts(ApiModel):
    watch_settings: int = 0
    origins: int = 0
    depots: int = 0
    organize_rules: int = 0
    transfer_rules: int = 0


class AdminClearedCounts(ApiModel):
    activity_events: int = 0
    transfer_jobs: int = 0
    tmdb_detail_cache: int = 0


class AdminRestoreResult(ApiModel):
    ok: bool = True
    restored: AdminRecordCounts
    cleared: AdminClearedCounts


class AdminRestoreRequest(ApiModel):
    content: str


class AdminWatchSettingsBackup(ApiModel):
    id: str = "main"
    path: Path
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdminOriginBackup(ApiModel):
    id: str
    name: str
    path: Path
    media_type: MediaType
    trigger: OriginTrigger
    policy: OrganizePolicy
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdminDepotBackup(ApiModel):
    id: str
    name: str
    path: Path
    media_type: MediaType
    policy: TransferPolicy
    resolve_mode: ResolveMode = ResolveMode.FULL
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdminTmdbProviderBackup(ApiModel):
    api_key: str | None = None
    base_url: str
    rate_limit: float = Field(gt=0)
    proxy: str | None = None


class AdminLlmProviderBackup(ApiModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    batch_size: int = Field(gt=0)
    rate_limit: float = Field(gt=0)
    proxy: str | None = None


class AdminProvidersBackup(ApiModel):
    tmdb: AdminTmdbProviderBackup
    llm: AdminLlmProviderBackup


class AdminBackup(ApiModel):
    model_config = ConfigDict(populate_by_name=True, use_enum_values=True, extra="forbid")

    format: Literal["omedia-config-backup"] = "omedia-config-backup"
    version: Literal[2] = 2
    exported_at: datetime
    organize: OrganizeSettings
    providers: AdminProvidersBackup
    watch_runtime: WatchRuntimeSettings | None = None
    watch_settings: AdminWatchSettingsBackup | None = None
    origins: list[AdminOriginBackup] = Field(default_factory=list)
    depots: list[AdminDepotBackup] = Field(default_factory=list)
    organize_rules: list[OrganizeRule] = Field(default_factory=list)
    transfer_rules: list[TransferRule] = Field(default_factory=list)
