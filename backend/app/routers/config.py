"""
Configuration Router
Handles application configuration management.
"""

import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class LLMConfigResponse(BaseModel):
    """LLM configuration response (without sensitive data)"""
    has_api_key: bool
    base_url: Optional[str]
    model: str
    batch_size: int
    rate_limit: int


class TMDBConfigResponse(BaseModel):
    """TMDB configuration response (without sensitive data)"""
    has_api_key: bool
    languages: List[str]
    rate_limit: int


class P115ConfigResponse(BaseModel):
    """115 configuration response (without sensitive data)"""
    has_cookies: bool
    share_receive_paths: List[str]


class StorageConfigResponse(BaseModel):
    """Storage configuration response"""
    local_media_paths: List[str]
    has_webdav: bool


class ConfigResponse(BaseModel):
    """Full configuration response"""
    app_name: str
    debug: bool
    llm: LLMConfigResponse
    tmdb: TMDBConfigResponse
    p115: P115ConfigResponse
    storage: StorageConfigResponse
    naming_presets: Dict[str, Any]
    version_tags: List[str]


class UpdateLLMConfigRequest(BaseModel):
    """Request to update LLM configuration"""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    batch_size: Optional[int] = None
    rate_limit: Optional[int] = None


class UpdateTMDBConfigRequest(BaseModel):
    """Request to update TMDB configuration"""
    api_key: Optional[str] = None
    languages: Optional[List[str]] = None
    rate_limit: Optional[int] = None


class UpdateP115ConfigRequest(BaseModel):
    """Request to update 115 configuration"""
    cookies: Optional[str] = None
    share_receive_paths: Optional[List[str]] = None


class UpdateStorageConfigRequest(BaseModel):
    """Request to update storage configuration"""
    local_media_paths: Optional[List[str]] = None
    webdav_url: Optional[str] = None
    webdav_username: Optional[str] = None
    webdav_password: Optional[str] = None


@router.get("/", response_model=ConfigResponse)
async def get_config():
    """
    Get current application configuration.
    
    Sensitive data (API keys, passwords) are masked.
    """
    return ConfigResponse(
        app_name=settings.app_name,
        debug=settings.debug,
        llm=LLMConfigResponse(
            has_api_key=bool(settings.llm.api_key),
            base_url=settings.llm.base_url,
            model=settings.llm.model,
            batch_size=settings.llm.batch_size,
            rate_limit=settings.llm.rate_limit
        ),
        tmdb=TMDBConfigResponse(
            has_api_key=bool(settings.tmdb.api_key),
            languages=settings.tmdb.languages,
            rate_limit=settings.tmdb.rate_limit
        ),
        p115=P115ConfigResponse(
            has_cookies=bool(settings.p115.cookies),
            share_receive_paths=settings.p115.share_receive_paths
        ),
        storage=StorageConfigResponse(
            local_media_paths=settings.storage.local_media_paths,
            has_webdav=bool(settings.storage.webdav_url)
        ),
        naming_presets=settings.naming_presets,
        version_tags=settings.version_tags
    )


@router.get("/naming-presets")
async def get_naming_presets():
    """Get available naming presets"""
    return settings.naming_presets


@router.get("/version-tags")
async def get_version_tags():
    """Get available version tags"""
    return settings.version_tags


@router.get("/template-variables")
async def get_template_variables():
    """
    Get available template variables for naming patterns.
    
    Returns a list of variables that can be used in naming patterns.
    """
    return {
        "common": [
            {"name": "title", "description": "Media title (from TMDB)"},
            {"name": "original_title", "description": "Original title (from TMDB)"},
            {"name": "year", "description": "Release year"},
            {"name": "tmdb_id", "description": "TMDB ID"},
            {"name": "quality", "description": "Quality (e.g., 1080p, 4K)"},
            {"name": "source", "description": "Source (e.g., BluRay, WEB-DL)"},
            {"name": "codec", "description": "Video codec (e.g., x264, HEVC)"},
            {"name": "audio", "description": "Audio codec (e.g., AAC, DTS)"},
            {"name": "release_group", "description": "Release group name"},
            {"name": "version", "description": "Version tag (e.g., [4K], [Director's Cut])"},
            {"name": "ext", "description": "File extension"},
        ],
        "tv_only": [
            {"name": "season", "description": "Season number (padded to 2 digits)"},
            {"name": "episode", "description": "Episode number (padded to 2 digits)"},
            {"name": "episode_title", "description": "Episode title (from TMDB)"},
        ],
        "formatting": [
            {"name": "{var}", "description": "Basic variable substitution"},
            {"name": "{var:02d}", "description": "Padded number (e.g., season:02d -> 01)"},
        ]
    }


@router.get("/rule-condition-fields")
async def get_rule_condition_fields():
    """
    Get available fields for transfer rule conditions.
    """
    return {
        "fields": [
            {
                "name": "genre",
                "description": "TMDB genre",
                "operators": ["contains", "equals", "in"],
                "example_values": ["Animation", "Documentary", "Drama", "Comedy"]
            },
            {
                "name": "country",
                "description": "Origin country code",
                "operators": ["equals", "in"],
                "example_values": ["JP", "CN", "KR", "US", "GB"]
            },
            {
                "name": "language",
                "description": "Original language code",
                "operators": ["equals", "in"],
                "example_values": ["ja", "zh", "ko", "en"]
            },
            {
                "name": "network",
                "description": "TV network (from TMDB)",
                "operators": ["contains", "equals", "in"],
                "example_values": ["Netflix", "HBO", "NHK", "BBC"]
            },
            {
                "name": "year_range",
                "description": "Release year range",
                "operators": ["between", "gte", "lte"],
                "example_values": [[2020, 2025], 2020, 2025]
            },
            {
                "name": "keyword",
                "description": "Filename keyword",
                "operators": ["contains", "matches"],
                "example_values": ["4K", "2160p", "UHD", "HEVC"]
            },
            {
                "name": "rating",
                "description": "TMDB rating",
                "operators": ["gte", "lte"],
                "example_values": [8.0, 7.0]
            }
        ],
        "operators": {
            "contains": "Field contains value",
            "equals": "Field equals value exactly",
            "in": "Field value is in list",
            "matches": "Field matches regex pattern",
            "between": "Field is between two values",
            "gte": "Field is greater than or equal to",
            "lte": "Field is less than or equal to"
        }
    }


# Note: In production, these update endpoints should be protected
# and may require restart to take effect for some settings.
# For now, they're just for reference/documentation.

@router.get("/status")
async def get_status():
    """
    Get application status.
    
    Checks connectivity to external services.
    """
    status = {
        "app": "running",
        "llm": "unconfigured",
        "tmdb": "unconfigured",
        "p115": "unconfigured"
    }
    
    # Check LLM
    if settings.llm.api_key:
        status["llm"] = "configured"
    
    # Check TMDB
    if settings.tmdb.api_key:
        status["tmdb"] = "configured"
    
    # Check 115
    if settings.p115.cookies:
        status["p115"] = "configured"
    
    return status

