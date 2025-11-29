"""
Share Link Import Router (Use Case 1)
Handles 115 share link parsing, file listing, and receiving.
"""

import re
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.schemas import (
    FileInfo, ShareLinkInfo, MediaType, RecognitionResult,
    StorageType
)
from ..vfs import get_vfs_adapter, P115Adapter, VFSError

logger = logging.getLogger(__name__)
router = APIRouter()


class ParseShareLinkRequest(BaseModel):
    """Request to parse a share link"""
    share_url: str = Field(..., description="115 share URL")


class ParseShareLinkResponse(BaseModel):
    """Response from parsing a share link"""
    share_code: str
    receive_code: Optional[str] = None
    files: List[FileInfo]
    is_single_media: bool = False
    detected_media_type: Optional[MediaType] = None


class SaveShareRequest(BaseModel):
    """Request to save files from share link"""
    share_code: str
    receive_code: Optional[str] = None
    target_path: str
    file_ids: Optional[List[str]] = None  # If None, save all files


class SaveShareResponse(BaseModel):
    """Response from saving share files"""
    success: bool
    message: str
    saved_count: int = 0


# Regex patterns for 115 share URLs
SHARE_URL_PATTERNS = [
    r"https?://(?:www\.)?115\.com/s/([a-zA-Z0-9]+)(?:\?password=([a-zA-Z0-9]+))?",
    r"115://share\|([a-zA-Z0-9]+)\|([a-zA-Z0-9]+)?",
]


def parse_share_url(url: str) -> tuple[str, Optional[str]]:
    """
    Parse 115 share URL to extract share code and receive code.
    
    Args:
        url: Share URL
        
    Returns:
        Tuple of (share_code, receive_code)
        
    Raises:
        ValueError: If URL format is invalid
    """
    for pattern in SHARE_URL_PATTERNS:
        match = re.search(pattern, url)
        if match:
            groups = match.groups()
            share_code = groups[0]
            receive_code = groups[1] if len(groups) > 1 else None
            return share_code, receive_code
    
    raise ValueError(f"Invalid share URL format: {url}")


def detect_media_type(files: List[FileInfo]) -> tuple[bool, Optional[MediaType]]:
    """
    Detect if the share contains a single media item and its type.
    
    Args:
        files: List of files from share
        
    Returns:
        Tuple of (is_single_media, detected_type)
    """
    # Video file extensions
    video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".m2ts"}
    
    # Count video files and check structure
    video_files = []
    video_folders = []
    
    for f in files:
        if f.is_dir:
            # Check if folder name looks like a TV show or movie
            name_lower = f.name.lower()
            if any(x in name_lower for x in ["season", "s0", "s1", "第", "季"]):
                video_folders.append(f)
        elif f.extension and f.extension.lower() in video_extensions:
            video_files.append(f)
    
    # Single video file
    if len(video_files) == 1 and not video_folders:
        return True, MediaType.MOVIE
    
    # Single folder (could be movie or TV show)
    if len(files) == 1 and files[0].is_dir:
        # Assume single folder is single media
        return True, MediaType.UNKNOWN
    
    # Multiple items - not single media
    return False, None


@router.post("/parse", response_model=ParseShareLinkResponse)
async def parse_share_link(request: ParseShareLinkRequest):
    """
    Parse a 115 share link and list its contents.
    
    This endpoint:
    1. Extracts share code and receive code from URL
    2. Lists files in the share
    3. Detects if it's a single media item
    """
    try:
        # Parse URL
        share_code, receive_code = parse_share_url(request.share_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    try:
        # Get 115 adapter
        adapter = get_vfs_adapter(StorageType.P115)
        
        # List share contents
        files = await adapter.list_share(share_code, receive_code)
        
        # Detect if single media
        is_single, media_type = detect_media_type(files)
        
        return ParseShareLinkResponse(
            share_code=share_code,
            receive_code=receive_code,
            files=files,
            is_single_media=is_single,
            detected_media_type=media_type
        )
        
    except VFSError as e:
        logger.error(f"Error parsing share link: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save", response_model=SaveShareResponse)
async def save_share_files(
    request: SaveShareRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Save files from a share link to 115 cloud storage.
    
    This endpoint:
    1. Receives files from share to target path
    2. Returns success status
    """
    try:
        # Get 115 adapter
        adapter = get_vfs_adapter(StorageType.P115)
        
        # Receive share
        success = await adapter.receive_share(
            share_code=request.share_code,
            receive_code=request.receive_code,
            target_path=request.target_path,
            file_ids=request.file_ids
        )
        
        if success:
            return SaveShareResponse(
                success=True,
                message="Files saved successfully",
                saved_count=len(request.file_ids) if request.file_ids else -1  # -1 means all files
            )
        else:
            return SaveShareResponse(
                success=False,
                message="Failed to save files",
                saved_count=0
            )
            
    except VFSError as e:
        logger.error(f"Error saving share files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/receive-paths")
async def get_receive_paths():
    """
    Get configured receive paths for share links.
    """
    from ..core.config import settings
    
    return {
        "paths": settings.p115.share_receive_paths
    }

