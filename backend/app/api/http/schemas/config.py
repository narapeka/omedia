from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field

from app.api.http.schemas.common import ApiModel
from app.domain.media import MediaType
from app.domain.origin import OriginTrigger
from app.domain.rule import RuleOperator


class SettingsHealth(ApiModel):
    ok: bool
    database: bool
    config_loaded: bool
    origins: int
    depots: int
    organize_rules: int = 0
    transfer_rules: int = 0
    watched_folders: int = 0
    scheduled_transfers: int = 0


class ProviderStatus(ApiModel):
    tmdb_api_key: str | None = None
    tmdb_base_url: str
    tmdb_rate_limit: float
    tmdb_proxy: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_batch_size: int
    llm_rate_limit: float
    llm_proxy: str | None = None


class ProviderSettingsUpdate(ApiModel):
    tmdb_api_key: str
    tmdb_base_url: str
    tmdb_rate_limit: float = Field(gt=0)
    tmdb_proxy: str | None = None
    llm_api_key: str
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_batch_size: int = Field(gt=0)
    llm_rate_limit: float = Field(gt=0)
    llm_proxy: str | None = None


class MediaExtensionSettings(ApiModel):
    video: list[str]
    subtitle: list[str]
    sidecar: list[str]


class WatchRuntimeSettings(ApiModel):
    poll_interval_seconds: float = Field(gt=0)
    stability_debounce_seconds: float = Field(gt=0)


class OrganizeSettings(ApiModel):
    extensions: MediaExtensionSettings
    min_non_subtitle_file_size_mb: int | None = Field(default=50, ge=0)


class OrganizePolicy(ApiModel):
    target_depot_id: str
    organize_rule_id: str | None = None


class OriginDraft(ApiModel):
    name: str
    path: Path
    media_type: MediaType
    trigger: OriginTrigger
    policy: OrganizePolicy
    enabled: bool = True


class Origin(OriginDraft):
    id: str


class OriginSummary(Origin):
    candidate_count: int = 0
    file_count: int = 0
    unknown_count: int = 0


class RuleCondition(ApiModel):
    field: str
    op: RuleOperator
    value: Any


class RuleCategory(ApiModel):
    name: str
    bucket: str
    conditions: list[RuleCondition] = Field(default_factory=list)


class OrganizeRuleDraft(ApiModel):
    name: str
    categories: list[RuleCategory] = Field(default_factory=list)
    fallback_bucket: str = ""
    description: str | None = None


class OrganizeRule(OrganizeRuleDraft):
    id: str


class TransferRuleDraft(OrganizeRuleDraft):
    pass


class TransferRule(TransferRuleDraft):
    id: str


class OrganizeRulePreviewRequest(ApiModel):
    rule: OrganizeRuleDraft | OrganizeRule
    relative_path: Path
    tmdb: dict[str, Any] | None = None


class TransferRulePreviewRequest(ApiModel):
    rule: TransferRuleDraft | TransferRule
    relative_path: Path


class RulePreview(ApiModel):
    bucket: str
    matched_category: str | None = None
    warnings: list[str] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    transfer_bucket: str | None = None
    organize_prefix: str | None = None
    media_relative_path: str | None = None
    destination_relative_path: str | None = None
    path_split_confidence: str | None = None


class RuleReferenceGenre(ApiModel):
    id: int
    name: str
    name_zh: str | None = None


class RuleReferenceCountry(ApiModel):
    iso_3166_1: str
    english_name: str
    native_name: str | None = None


class RuleReferences(ApiModel):
    movie_genres: list[RuleReferenceGenre] = Field(default_factory=list)
    tv_genres: list[RuleReferenceGenre] = Field(default_factory=list)
    countries: list[RuleReferenceCountry]
    source: str = "bundled"
