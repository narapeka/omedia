"""
Transfer Rules Router
Handles CRUD operations for transfer rules and naming patterns.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..core.database import get_db
from ..models.schemas import TransferRule, RuleCondition, StorageType, MediaType
from ..models.db_models import TransferRuleDB, NamingPatternDB, VersionTagDB

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateRuleRequest(BaseModel):
    """Request to create a transfer rule"""
    name: str
    priority: int = 100
    media_type: str = "all"  # movie, tv, all
    storage_type: str = "all"  # p115, local, webdav, all
    conditions: List[RuleCondition] = Field(default_factory=list)
    target_path: str
    naming_pattern: Optional[str] = None
    enabled: bool = True


class UpdateRuleRequest(BaseModel):
    """Request to update a transfer rule"""
    name: Optional[str] = None
    priority: Optional[int] = None
    media_type: Optional[str] = None
    storage_type: Optional[str] = None
    conditions: Optional[List[RuleCondition]] = None
    target_path: Optional[str] = None
    naming_pattern: Optional[str] = None
    enabled: Optional[bool] = None


class RuleResponse(BaseModel):
    """Transfer rule response"""
    id: str
    name: str
    priority: int
    media_type: str
    storage_type: str
    conditions: List[dict]
    target_path: str
    naming_pattern: Optional[str]
    enabled: bool
    
    class Config:
        from_attributes = True


class RuleListResponse(BaseModel):
    """Response for rule listing"""
    rules: List[RuleResponse]
    total: int


# ============ Transfer Rules ============

@router.get("/", response_model=RuleListResponse)
async def list_rules(
    media_type: Optional[str] = None,
    storage_type: Optional[str] = None,
    enabled_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    List all transfer rules.
    
    Optionally filter by media type, storage type, or enabled status.
    Rules are returned ordered by priority (lowest first).
    """
    query = select(TransferRuleDB).order_by(TransferRuleDB.priority)
    
    if media_type:
        query = query.where(
            (TransferRuleDB.media_type == media_type) | 
            (TransferRuleDB.media_type == "all")
        )
    if storage_type:
        query = query.where(
            (TransferRuleDB.storage_type == storage_type) | 
            (TransferRuleDB.storage_type == "all")
        )
    if enabled_only:
        query = query.where(TransferRuleDB.enabled == True)
    
    result = await db.execute(query)
    rules = result.scalars().all()
    
    return RuleListResponse(
        rules=[RuleResponse.model_validate(r) for r in rules],
        total=len(rules)
    )


@router.post("/", response_model=RuleResponse)
async def create_rule(
    request: CreateRuleRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new transfer rule"""
    # Convert conditions to dict format for JSON storage
    conditions_data = [c.model_dump() for c in request.conditions]
    
    rule = TransferRuleDB(
        name=request.name,
        priority=request.priority,
        media_type=request.media_type,
        storage_type=request.storage_type,
        conditions=conditions_data,
        target_path=request.target_path,
        naming_pattern=request.naming_pattern,
        enabled=request.enabled
    )
    
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    
    return RuleResponse.model_validate(rule)


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific rule by ID"""
    result = await db.execute(select(TransferRuleDB).where(TransferRuleDB.id == rule_id))
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return RuleResponse.model_validate(rule)


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    request: UpdateRuleRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update a transfer rule"""
    result = await db.execute(select(TransferRuleDB).where(TransferRuleDB.id == rule_id))
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Update fields
    if request.name is not None:
        rule.name = request.name
    if request.priority is not None:
        rule.priority = request.priority
    if request.media_type is not None:
        rule.media_type = request.media_type
    if request.storage_type is not None:
        rule.storage_type = request.storage_type
    if request.conditions is not None:
        rule.conditions = [c.model_dump() for c in request.conditions]
    if request.target_path is not None:
        rule.target_path = request.target_path
    if request.naming_pattern is not None:
        rule.naming_pattern = request.naming_pattern
    if request.enabled is not None:
        rule.enabled = request.enabled
    
    await db.commit()
    await db.refresh(rule)
    
    return RuleResponse.model_validate(rule)


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a transfer rule"""
    result = await db.execute(select(TransferRuleDB).where(TransferRuleDB.id == rule_id))
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    await db.delete(rule)
    await db.commit()
    
    return {"message": "Rule deleted successfully"}


# ============ Naming Patterns ============

@router.get("/patterns/")
async def list_naming_patterns(
    media_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all naming patterns"""
    query = select(NamingPatternDB)
    
    if media_type:
        query = query.where(
            (NamingPatternDB.media_type == media_type) | 
            (NamingPatternDB.media_type == "all")
        )
    
    result = await db.execute(query)
    patterns = result.scalars().all()
    
    # Include built-in presets
    from ..core.config import settings
    presets = [
        {
            "id": f"preset_{name}",
            "name": name,
            "is_preset": True,
            **pattern
        }
        for name, pattern in settings.naming_presets.items()
    ]
    
    return {
        "patterns": [
            {
                "id": p.id,
                "name": p.name,
                "media_type": p.media_type,
                "folder_pattern": p.folder_pattern,
                "file_pattern": p.file_pattern,
                "season_folder_pattern": p.season_folder_pattern,
                "is_default": p.is_default,
                "is_preset": False
            }
            for p in patterns
        ],
        "presets": presets
    }


@router.post("/patterns/")
async def create_naming_pattern(
    name: str,
    media_type: str,
    folder_pattern: str,
    file_pattern: str,
    season_folder_pattern: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Create a custom naming pattern"""
    pattern = NamingPatternDB(
        name=name,
        media_type=media_type,
        folder_pattern=folder_pattern,
        file_pattern=file_pattern,
        season_folder_pattern=season_folder_pattern
    )
    
    db.add(pattern)
    await db.commit()
    await db.refresh(pattern)
    
    return pattern


# ============ Version Tags ============

@router.get("/version-tags/")
async def list_version_tags(
    db: AsyncSession = Depends(get_db)
):
    """List all version tags"""
    result = await db.execute(select(VersionTagDB))
    custom_tags = result.scalars().all()
    
    # Include built-in tags
    from ..core.config import settings
    
    return {
        "builtin_tags": settings.version_tags,
        "custom_tags": [t.tag for t in custom_tags]
    }


@router.post("/version-tags/")
async def create_version_tag(
    tag: str,
    db: AsyncSession = Depends(get_db)
):
    """Create a custom version tag"""
    # Check if tag already exists
    result = await db.execute(select(VersionTagDB).where(VersionTagDB.tag == tag))
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Tag already exists")
    
    new_tag = VersionTagDB(tag=tag)
    db.add(new_tag)
    await db.commit()
    
    return {"message": "Tag created", "tag": tag}


@router.delete("/version-tags/{tag}")
async def delete_version_tag(
    tag: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a custom version tag"""
    result = await db.execute(select(VersionTagDB).where(VersionTagDB.tag == tag))
    existing = result.scalar_one_or_none()
    
    if not existing:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    await db.delete(existing)
    await db.commit()
    
    return {"message": "Tag deleted"}

