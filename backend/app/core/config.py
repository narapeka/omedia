"""
Configuration management for OMedia
Loads settings from environment variables and config files.
"""

import os
from pathlib import Path
from typing import Optional, List, Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    """LLM API configuration"""
    model_config = SettingsConfigDict(env_prefix="LLM_")
    
    api_key: str = Field(default="", description="OpenAI-compatible API key")
    base_url: Optional[str] = Field(default=None, description="Custom API base URL")
    model: str = Field(default="gpt-4o-mini", description="Model name")
    batch_size: int = Field(default=50, description="Batch size for extraction")
    rate_limit: int = Field(default=2, description="Max requests per second")


class TMDBSettings(BaseSettings):
    """TMDB API configuration"""
    model_config = SettingsConfigDict(env_prefix="TMDB_")
    
    api_key: str = Field(default="", description="TMDB API key")
    languages: List[str] = Field(
        default=["zh-CN", "zh-SG", "zh-TW", "zh-HK"],
        description="Languages to try when searching"
    )
    rate_limit: int = Field(default=40, description="Max requests per second")


class P115Settings(BaseSettings):
    """115 Cloud Storage configuration"""
    model_config = SettingsConfigDict(env_prefix="P115_")
    
    cookies: str = Field(default="", description="115 cookies string")
    # Default paths for different use cases
    share_receive_paths: List[str] = Field(
        default=[],
        description="Target paths for receiving shared files"
    )


class StorageSettings(BaseSettings):
    """Storage configuration"""
    model_config = SettingsConfigDict(env_prefix="STORAGE_")
    
    # Local storage paths
    local_media_paths: List[str] = Field(
        default=[],
        description="Local media library paths"
    )
    # WebDAV configuration
    webdav_url: Optional[str] = Field(default=None, description="WebDAV server URL")
    webdav_username: Optional[str] = Field(default=None, description="WebDAV username")
    webdav_password: Optional[str] = Field(default=None, description="WebDAV password")


class Settings(BaseSettings):
    """Main application settings"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Application settings
    app_name: str = Field(default="OMedia", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    
    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./omedia.db",
        description="Database connection URL"
    )
    
    # Security
    secret_key: str = Field(
        default="change-me-in-production",
        description="Secret key for security"
    )
    
    # API settings
    api_prefix: str = Field(default="/api/v1", description="API route prefix")
    
    # Proxy settings
    proxy_host: Optional[str] = Field(default=None, description="Proxy host")
    proxy_port: Optional[int] = Field(default=None, description="Proxy port")
    
    # Sub-configurations
    llm: LLMSettings = Field(default_factory=LLMSettings)
    tmdb: TMDBSettings = Field(default_factory=TMDBSettings)
    p115: P115Settings = Field(default_factory=P115Settings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    
    # Naming patterns presets
    naming_presets: dict = Field(default_factory=lambda: {
        "emby_standard": {
            "movie_folder": "{title} ({year}) {{tmdb-{tmdb_id}}}",
            "movie_file": "{title} ({year}){version}.{ext}",
            "tv_folder": "{title} ({year}) {{tmdb-{tmdb_id}}}",
            "tv_season_folder": "Season {season:02d}",
            "tv_episode_file": "{title} - S{season:02d}E{episode:02d} - {episode_title}.{ext}"
        },
        "plex_standard": {
            "movie_folder": "{title} ({year})",
            "movie_file": "{title} ({year}){version}.{ext}",
            "tv_folder": "{title} ({year})",
            "tv_season_folder": "Season {season:02d}",
            "tv_episode_file": "{title} - S{season:02d}E{episode:02d}.{ext}"
        }
    })
    
    # Version tags presets
    version_tags: List[str] = Field(default_factory=lambda: [
        "[4K]",
        "[1080p]",
        "[Director's Cut]",
        "[Extended]",
        "[Theatrical]",
        "[Remastered]",
        "[HDR]",
        "[IMAX]"
    ])
    
    @property
    def data_dir(self) -> Path:
        """Get data directory path"""
        data_dir = Path(os.getenv("DATA_DIR", "./data"))
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
    
    @property
    def logs_dir(self) -> Path:
        """Get logs directory path"""
        logs_dir = self.data_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir
    
    @property
    def cache_dir(self) -> Path:
        """Get cache directory path"""
        cache_dir = self.data_dir / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir


# Global settings instance
settings = Settings()

