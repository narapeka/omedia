"""
Pydantic schemas for API models
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class MediaType(str, Enum):
    """Media type enumeration"""
    MOVIE = "movie"
    TV = "tv"
    UNKNOWN = "unknown"


class StorageType(str, Enum):
    """Storage type enumeration"""
    LOCAL = "local"
    P115 = "p115"
    WEBDAV = "webdav"


class ConfidenceLevel(str, Enum):
    """Recognition confidence level"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TransferStatus(str, Enum):
    """Transfer task status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStatus(str, Enum):
    """Job status"""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


# ============ File and Media Models ============

class FileInfo(BaseModel):
    """Information about a file"""
    name: str
    path: str
    size: int = 0
    is_dir: bool = False
    extension: Optional[str] = None
    modified_time: Optional[datetime] = None
    # 115 specific
    pickcode: Optional[str] = None
    file_id: Optional[str] = None
    # Storage info
    storage_type: StorageType = StorageType.LOCAL
    
    class Config:
        from_attributes = True


class TMDBInfo(BaseModel):
    """TMDB metadata"""
    tmdb_id: int
    title: str
    original_title: Optional[str] = None
    year: Optional[int] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    # TV specific
    seasons: Optional[List[Dict[str, Any]]] = None
    # Movie specific
    runtime: Optional[int] = None
    # Category fields
    genre_ids: Optional[List[int]] = None
    origin_country: Optional[List[str]] = None
    original_language: Optional[str] = None


class MediaInfo(BaseModel):
    """Recognized media information"""
    media_type: MediaType
    title: str
    original_title: Optional[str] = None
    year: Optional[int] = None
    # TV specific
    season: Optional[int] = None
    episode: Optional[int] = None
    end_episode: Optional[int] = None
    episode_title: Optional[str] = None
    # TMDB data
    tmdb_id: Optional[int] = None
    tmdb_info: Optional[TMDBInfo] = None
    # Extracted from filename
    quality: Optional[str] = None  # 1080p, 4K, etc.
    source: Optional[str] = None  # BluRay, WEB-DL, etc.
    codec: Optional[str] = None  # x264, HEVC, etc.
    audio: Optional[str] = None  # AAC, DTS, etc.
    release_group: Optional[str] = None


class RecognitionResult(BaseModel):
    """Result of media recognition"""
    file_info: FileInfo
    media_info: Optional[MediaInfo] = None
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    # LLM extraction results
    llm_extracted: Optional[Dict[str, Any]] = None
    # Matched transfer rule
    matched_rule_id: Optional[str] = None
    matched_rule_name: Optional[str] = None
    # Target path
    target_path: Optional[str] = None
    target_folder_name: Optional[str] = None
    target_file_name: Optional[str] = None
    # User override
    user_override: bool = False
    version_tag: Optional[str] = None


# ============ Transfer Rules Models ============

class RuleCondition(BaseModel):
    """Condition for transfer rule matching"""
    field: str  # genre, country, language, keyword, year_range, network, rating
    operator: str  # contains, equals, in, matches, between, gte, lte
    value: Any


class TransferRule(BaseModel):
    """Transfer routing rule"""
    id: Optional[str] = None
    name: str
    priority: int = 100  # Lower = higher priority
    media_type: Literal["movie", "tv", "all"] = "all"
    storage_type: Literal["p115", "local", "webdav", "all"] = "all"
    conditions: List[RuleCondition] = Field(default_factory=list)
    target_path: str  # Path template with variables
    naming_pattern: Optional[str] = None  # Optional custom naming pattern
    enabled: bool = True
    
    class Config:
        from_attributes = True


class NamingPattern(BaseModel):
    """Naming pattern configuration"""
    id: Optional[str] = None
    name: str
    media_type: Literal["movie", "tv", "all"] = "all"
    folder_pattern: str
    file_pattern: str
    # For TV shows
    season_folder_pattern: Optional[str] = None
    is_default: bool = False


# ============ Job Models ============

class Job(BaseModel):
    """Monitoring job configuration"""
    id: Optional[str] = None
    name: str
    job_type: Literal["watchdog", "life_event"]
    source_path: str
    storage_type: StorageType
    # Target configuration
    default_rule_ids: Optional[List[str]] = None  # Specific rules for this job
    auto_approve: bool = False  # Auto-transfer high confidence results
    confidence_threshold: ConfidenceLevel = ConfidenceLevel.HIGH
    # Job settings
    enabled: bool = True
    status: JobStatus = JobStatus.ACTIVE
    # Watchdog specific
    poll_interval: int = 60  # seconds
    # Life event specific
    event_types: Optional[List[str]] = None
    
    class Config:
        from_attributes = True


class TransferTask(BaseModel):
    """Transfer task"""
    id: Optional[str] = None
    job_id: Optional[str] = None
    source_path: str
    target_path: str
    storage_type: StorageType
    # Media info
    media_type: MediaType
    media_title: Optional[str] = None
    tmdb_id: Optional[str] = None
    # Transfer info
    matched_rule_id: Optional[str] = None
    status: TransferStatus = TransferStatus.PENDING
    error_message: Optional[str] = None
    user_override: bool = False
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# ============ Share Link Models ============

class ShareLinkInfo(BaseModel):
    """115 share link information"""
    share_code: str
    receive_code: Optional[str] = None
    # Extracted files
    files: List[FileInfo] = Field(default_factory=list)
    # Detection result
    is_single_media: bool = False
    detected_media_type: Optional[MediaType] = None


# ============ API Request/Response Models ============

class RecognizeRequest(BaseModel):
    """Request for media recognition"""
    files: List[FileInfo]
    media_type: MediaType
    storage_type: StorageType


class RecognizeResponse(BaseModel):
    """Response from media recognition"""
    results: List[RecognitionResult]
    errors: List[Dict[str, str]] = Field(default_factory=list)


class ReIdentifyRequest(BaseModel):
    """Request for manual re-identification"""
    file_path: str
    search_term: Optional[str] = None
    year: Optional[int] = None
    tmdb_id: Optional[int] = None
    media_type: MediaType = MediaType.TV


class TMDBSearchRequest(BaseModel):
    """Request for TMDB search"""
    query: str
    year: Optional[int] = None
    media_type: MediaType = MediaType.TV


class TMDBSearchResult(BaseModel):
    """TMDB search result"""
    tmdb_id: int
    title: str
    original_title: Optional[str] = None
    year: Optional[int] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    media_type: MediaType


class TransferRequest(BaseModel):
    """Request for file transfer"""
    items: List[RecognitionResult]
    global_rule_override: Optional[str] = None  # Override all items with this rule


class ShareLinkRequest(BaseModel):
    """Request for share link import"""
    share_url: str
    target_path: Optional[str] = None


class DryRunReport(BaseModel):
    """Dry run report for batch operations"""
    total_items: int
    recognized_items: int
    high_confidence: int
    medium_confidence: int
    low_confidence: int
    items: List[RecognitionResult]
    errors: List[Dict[str, str]] = Field(default_factory=list)

