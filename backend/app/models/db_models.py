"""
SQLAlchemy ORM models for database tables
"""

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    String, Integer, Boolean, DateTime, Text, JSON, Float, ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base


def generate_uuid() -> str:
    """Generate a UUID string"""
    return str(uuid.uuid4())


class TransferRuleDB(Base):
    """Transfer rules table"""
    __tablename__ = "transfer_rules"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    media_type: Mapped[str] = mapped_column(String(10), default="all")  # movie, tv, all
    storage_type: Mapped[str] = mapped_column(String(10), default="all")  # p115, local, webdav, all
    conditions: Mapped[dict] = mapped_column(JSON, default=list)  # List of RuleCondition
    target_path: Mapped[str] = mapped_column(Text, nullable=False)
    naming_pattern: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    def __repr__(self) -> str:
        return f"<TransferRule {self.name} (priority={self.priority})>"


class JobDB(Base):
    """Monitoring jobs table"""
    __tablename__ = "jobs"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_type: Mapped[str] = mapped_column(String(20), nullable=False)  # watchdog, life_event
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    storage_type: Mapped[str] = mapped_column(String(10), nullable=False)  # local, p115
    default_rule_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence_threshold: Mapped[str] = mapped_column(String(10), default="high")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, paused, disabled
    # Watchdog specific
    poll_interval: Mapped[int] = mapped_column(Integer, default=60)
    # Life event specific
    event_types: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    def __repr__(self) -> str:
        return f"<Job {self.name} ({self.job_type})>"


class TransferHistoryDB(Base):
    """Transfer history table"""
    __tablename__ = "transfer_history"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    job_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    target_path: Mapped[str] = mapped_column(Text, nullable=False)
    storage_type: Mapped[str] = mapped_column(String(10), nullable=False)
    # Media info
    media_type: Mapped[str] = mapped_column(String(10), nullable=False)
    media_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tmdb_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Transfer info
    matched_rule_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("transfer_rules.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_override: Mapped[bool] = mapped_column(Boolean, default=False)
    # File info
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    job: Mapped[Optional["JobDB"]] = relationship("JobDB", backref="transfers")
    rule: Mapped[Optional["TransferRuleDB"]] = relationship("TransferRuleDB")
    
    def __repr__(self) -> str:
        return f"<TransferHistory {self.source_path} -> {self.target_path}>"


class RecognitionCacheDB(Base):
    """Recognition cache table to avoid re-processing"""
    __tablename__ = "recognition_cache"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    # File identification (hash of filename + size)
    file_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Recognition results
    media_type: Mapped[str] = mapped_column(String(10), nullable=False)
    tmdb_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    recognition_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    def __repr__(self) -> str:
        return f"<RecognitionCache {self.file_name} ({self.media_type})>"


class NamingPatternDB(Base):
    """Custom naming patterns table"""
    __tablename__ = "naming_patterns"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    media_type: Mapped[str] = mapped_column(String(10), default="all")  # movie, tv, all
    folder_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    file_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    season_folder_pattern: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    def __repr__(self) -> str:
        return f"<NamingPattern {self.name}>"


class VersionTagDB(Base):
    """Custom version tags table"""
    __tablename__ = "version_tags"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    tag: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<VersionTag {self.tag}>"

