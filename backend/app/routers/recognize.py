"""
Recognition Router
Handles media recognition, TMDB search, and re-identification.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..models.schemas import (
    MediaType, RecognitionResult, TMDBSearchResult,
    ReIdentifyRequest, TMDBSearchRequest, FileInfo
)

logger = logging.getLogger(__name__)
router = APIRouter()


class RecognizeFilesRequest(BaseModel):
    """Request to recognize multiple files"""
    files: List[FileInfo]
    media_type: MediaType


class RecognizeFilesResponse(BaseModel):
    """Response from file recognition"""
    results: List[RecognitionResult]
    errors: List[dict] = Field(default_factory=list)


class TMDBSearchResponse(BaseModel):
    """Response from TMDB search"""
    results: List[TMDBSearchResult]
    total: int


@router.post("/files", response_model=RecognizeFilesResponse)
async def recognize_files(
    request: RecognizeFilesRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Recognize media files.
    
    Performs:
    1. LLM extraction of title, year, season/episode
    2. TMDB lookup with confidence scoring
    3. Transfer rule matching
    
    Returns recognition results for each file.
    """
    from ..services.recognizer import RecognitionService
    
    service = RecognitionService()
    
    try:
        results = await service.recognize_files(
            request.files,
            request.media_type,
            db
        )
        return RecognizeFilesResponse(results=results, errors=[])
    except Exception as e:
        logger.error(f"Recognition failed: {e}")
        return RecognizeFilesResponse(
            results=[],
            errors=[{"error": str(e)}]
        )
    finally:
        await service.close()


@router.post("/re-identify", response_model=RecognitionResult)
async def re_identify_media(
    request: ReIdentifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Re-identify a media item.
    
    Allows user to manually correct recognition by:
    - Providing a search term
    - Specifying year
    - Directly providing TMDB ID
    """
    from ..services.recognizer import RecognitionService
    
    service = RecognitionService()
    
    try:
        # Create FileInfo from path
        file_info = FileInfo(
            name=request.file_path.split("/")[-1],
            path=request.file_path,
            size=0,
            is_dir=False
        )
        
        result = await service.re_identify(
            file_info=file_info,
            media_type=request.media_type,
            db=db,
            search_term=request.search_term,
            year=request.year,
            tmdb_id=request.tmdb_id
        )
        return result
    except Exception as e:
        logger.error(f"Re-identification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await service.close()


@router.post("/search-tmdb", response_model=TMDBSearchResponse)
async def search_tmdb(
    request: TMDBSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Search TMDB for media.
    
    Used for manual re-identification when auto-recognition fails.
    """
    from ..services.recognizer import RecognitionService
    
    service = RecognitionService()
    
    try:
        results = await service.search_tmdb(
            query=request.query,
            media_type=request.media_type,
            year=request.year
        )
        
        # Convert to response format
        search_results = [
            TMDBSearchResult(
                tmdb_id=r.tmdb_id,
                title=r.title,
                original_title=r.original_title,
                year=r.year,
                overview=r.overview,
                poster_path=r.poster_path,
                media_type=request.media_type
            )
            for r in results
        ]
        
        return TMDBSearchResponse(
            results=search_results,
            total=len(search_results)
        )
    except Exception as e:
        logger.error(f"TMDB search failed: {e}")
        return TMDBSearchResponse(results=[], total=0)
    finally:
        await service.close()


@router.get("/tmdb/{media_type}/{tmdb_id}")
async def get_tmdb_details(
    media_type: MediaType,
    tmdb_id: int
):
    """
    Get detailed information from TMDB for a specific item.
    """
    # TODO: Implement with TMDB service
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/cache/{file_hash}")
async def get_cached_recognition(
    file_hash: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get cached recognition result for a file.
    
    Uses file hash (filename + size) to lookup cached results.
    """
    from ..models.db_models import RecognitionCacheDB
    from sqlalchemy import select
    
    result = await db.execute(
        select(RecognitionCacheDB).where(RecognitionCacheDB.file_hash == file_hash)
    )
    cached = result.scalar_one_or_none()
    
    if not cached:
        raise HTTPException(status_code=404, detail="No cached recognition found")
    
    return {
        "file_hash": cached.file_hash,
        "file_name": cached.file_name,
        "media_type": cached.media_type,
        "tmdb_id": cached.tmdb_id,
        "confidence": cached.confidence,
        "recognition_data": cached.recognition_data,
        "created_at": cached.created_at
    }


@router.delete("/cache/{file_hash}")
async def clear_cached_recognition(
    file_hash: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Clear cached recognition for a file.
    
    Useful when file has been incorrectly recognized.
    """
    from ..models.db_models import RecognitionCacheDB
    from sqlalchemy import select
    
    result = await db.execute(
        select(RecognitionCacheDB).where(RecognitionCacheDB.file_hash == file_hash)
    )
    cached = result.scalar_one_or_none()
    
    if cached:
        await db.delete(cached)
        await db.commit()
    
    return {"message": "Cache cleared"}


@router.delete("/cache")
async def clear_all_cache(
    db: AsyncSession = Depends(get_db)
):
    """
    Clear all recognition cache.
    """
    from ..models.db_models import RecognitionCacheDB
    from sqlalchemy import delete
    
    await db.execute(delete(RecognitionCacheDB))
    await db.commit()
    
    return {"message": "All cache cleared"}

