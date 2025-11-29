"""
Manual Organize Router (Use Case 2)
Handles browsing, recognition, and organizing of media files.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.schemas import (
    FileInfo, MediaType, StorageType, RecognitionResult,
    DryRunReport, TransferRequest, ConfidenceLevel
)
from ..vfs import get_vfs_adapter, VFSError

logger = logging.getLogger(__name__)
router = APIRouter()


class BrowseRequest(BaseModel):
    """Request to browse a directory"""
    path: str
    storage_type: StorageType


class BrowseResponse(BaseModel):
    """Response from browsing a directory"""
    path: str
    storage_type: StorageType
    items: List[FileInfo]
    parent_path: Optional[str] = None


class StartOrganizeRequest(BaseModel):
    """Request to start organize process"""
    source_path: str
    storage_type: StorageType
    media_type: MediaType  # User must specify movie or TV


class OrganizeProgressResponse(BaseModel):
    """Progress of organize operation"""
    total: int
    processed: int
    current_file: Optional[str] = None
    status: str  # scanning, recognizing, ready, transferring, completed


class TransferResponse(BaseModel):
    """Response from transfer operation"""
    success: bool
    transferred_count: int
    failed_count: int
    errors: List[dict] = Field(default_factory=list)


@router.post("/browse", response_model=BrowseResponse)
async def browse_directory(request: BrowseRequest):
    """
    Browse a directory in the specified storage.
    
    Supports:
    - Local filesystem
    - 115 cloud storage
    - WebDAV (future)
    """
    try:
        adapter = get_vfs_adapter(request.storage_type)
        items = await adapter.list_dir(request.path)
        
        # Get parent path
        parent_path = adapter.get_parent(request.path)
        if parent_path == request.path:
            parent_path = None
        
        return BrowseResponse(
            path=request.path,
            storage_type=request.storage_type,
            items=items,
            parent_path=parent_path
        )
        
    except VFSError as e:
        logger.error(f"Error browsing directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan")
async def scan_for_media(request: StartOrganizeRequest):
    """
    Scan a directory for media files.
    
    Returns a list of files that can be organized.
    This does not perform recognition yet.
    """
    try:
        adapter = get_vfs_adapter(request.storage_type)
        
        # Video extensions
        video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".m2ts"}
        
        files = []
        async for item in adapter.walk(request.source_path, files_only=True):
            if item.extension and item.extension.lower() in video_extensions:
                files.append(item)
        
        return {
            "source_path": request.source_path,
            "storage_type": request.storage_type,
            "media_type": request.media_type,
            "file_count": len(files),
            "files": files
        }
        
    except VFSError as e:
        logger.error(f"Error scanning directory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recognize")
async def recognize_media(
    request: StartOrganizeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Recognize media files in a directory.
    
    This performs:
    1. Scanning for media files
    2. LLM extraction of metadata
    3. TMDB lookup
    4. Rule matching for target paths
    
    Returns a dry-run report for user confirmation.
    """
    # This will be implemented in the services layer
    # For now, return a placeholder
    return {
        "status": "processing",
        "message": "Recognition started. Check progress endpoint for status."
    }


@router.get("/progress/{task_id}")
async def get_organize_progress(task_id: str):
    """
    Get progress of an organize operation.
    """
    # This will track background tasks
    return OrganizeProgressResponse(
        total=0,
        processed=0,
        current_file=None,
        status="pending"
    )


@router.post("/dry-run", response_model=DryRunReport)
async def get_dry_run_report(
    request: StartOrganizeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a dry-run report of what would be organized.
    
    Shows:
    - Total items found
    - Recognition results with confidence levels
    - Matched transfer rules
    - Target paths
    """
    # Placeholder - will be implemented with recognition service
    return DryRunReport(
        total_items=0,
        recognized_items=0,
        high_confidence=0,
        medium_confidence=0,
        low_confidence=0,
        items=[],
        errors=[]
    )


@router.post("/transfer", response_model=TransferResponse)
async def execute_transfer(
    request: TransferRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Execute the transfer of recognized media files.
    
    Only transfers items that have been confirmed by the user.
    Respects storage type constraints (same-storage-only transfers).
    """
    # Placeholder - will be implemented with transfer service
    return TransferResponse(
        success=True,
        transferred_count=0,
        failed_count=0,
        errors=[]
    )


@router.get("/rules-for-storage")
async def get_rules_for_storage(
    storage_type: StorageType = Query(...),
    media_type: Optional[MediaType] = None
):
    """
    Get transfer rules applicable to a storage type.
    
    Used to show available target options in the UI.
    """
    # Placeholder - will query rules from database
    return {
        "storage_type": storage_type,
        "media_type": media_type,
        "rules": []
    }

