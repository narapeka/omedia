"""
Recognition Service
Orchestrates LLM extraction, TMDB lookup, and caching.
"""

import hashlib
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .llm_agent import LLMAgent, ExtractedMediaInfo
from .tmdb_client import TMDBClient, TMDBResult
from .pattern_extractor import PatternExtractor
from ...models.schemas import (
    MediaType, ConfidenceLevel, FileInfo, MediaInfo, RecognitionResult, TMDBInfo
)
from ...models.db_models import RecognitionCacheDB
from ...core.config import settings
from ...core.events import event_bus, EventType

logger = logging.getLogger(__name__)


class RecognitionService:
    """
    Service for recognizing media files.
    Combines LLM extraction, TMDB lookup, pattern extraction, and caching.
    """
    
    def __init__(self):
        self.llm_agent = LLMAgent()
        self.tmdb_client = TMDBClient()
        self.pattern_extractor = PatternExtractor()
    
    async def recognize_files(
        self,
        files: List[FileInfo],
        media_type: MediaType,
        db: AsyncSession
    ) -> List[RecognitionResult]:
        """
        Recognize multiple media files.
        
        Args:
            files: List of FileInfo objects
            media_type: Expected media type (movie or tv)
            db: Database session for caching
            
        Returns:
            List of RecognitionResult objects
        """
        await event_bus.emit(
            EventType.RECOGNITION_STARTED,
            {"file_count": len(files), "media_type": media_type.value}
        )
        
        results = []
        
        for file_info in files:
            try:
                result = await self.recognize_single(
                    file_info,
                    media_type,
                    db
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error recognizing {file_info.name}: {e}")
                results.append(RecognitionResult(
                    file_info=file_info,
                    confidence=ConfidenceLevel.LOW
                ))
        
        # Calculate summary
        high_count = sum(1 for r in results if r.confidence == ConfidenceLevel.HIGH)
        low_count = sum(1 for r in results if r.confidence == ConfidenceLevel.LOW)
        
        await event_bus.emit(
            EventType.RECOGNITION_COMPLETED,
            {
                "total": len(results),
                "high_confidence": high_count,
                "low_confidence": low_count
            }
        )
        
        return results
    
    async def recognize_single(
        self,
        file_info: FileInfo,
        media_type: MediaType,
        db: AsyncSession
    ) -> RecognitionResult:
        """
        Recognize a single media file.
        
        Args:
            file_info: File information
            media_type: Expected media type
            db: Database session
            
        Returns:
            RecognitionResult
        """
        filename = file_info.name
        
        # Check cache first
        file_hash = self._compute_file_hash(filename, file_info.size)
        cached = await self._get_cached_result(db, file_hash)
        
        if cached:
            logger.debug(f"Using cached result for {filename}")
            return self._cached_to_result(file_info, cached)
        
        # Extract patterns first (fast)
        pattern_result = self.pattern_extractor.extract(filename)
        
        # Use LLM for title extraction
        llm_result = await self.llm_agent.extract_single(
            filename,
            media_type.value if media_type != MediaType.UNKNOWN else "unknown"
        )
        
        # Determine search query
        search_query = self._build_search_query(llm_result, filename)
        search_year = llm_result.year or pattern_result.year
        
        # Search TMDB
        tmdb_type = "movie" if media_type == MediaType.MOVIE else "tv"
        tmdb_result = await self.tmdb_client.find_best_match(
            search_query,
            tmdb_type,
            search_year,
            filename
        )
        
        # Build result
        result = self._build_recognition_result(
            file_info,
            llm_result,
            tmdb_result,
            pattern_result,
            media_type
        )
        
        # Cache result
        await self._cache_result(db, file_hash, filename, file_info.size, result)
        
        return result
    
    async def re_identify(
        self,
        file_info: FileInfo,
        media_type: MediaType,
        db: AsyncSession,
        search_term: Optional[str] = None,
        year: Optional[int] = None,
        tmdb_id: Optional[int] = None
    ) -> RecognitionResult:
        """
        Re-identify a media file with user-provided hints.
        
        Args:
            file_info: File information
            media_type: Media type
            db: Database session
            search_term: User-provided search term
            year: User-provided year
            tmdb_id: User-provided TMDB ID (overrides search)
            
        Returns:
            Updated RecognitionResult
        """
        tmdb_result: Optional[TMDBResult] = None
        tmdb_type = "movie" if media_type == MediaType.MOVIE else "tv"
        
        if tmdb_id:
            # Direct lookup by ID
            if media_type == MediaType.MOVIE:
                tmdb_result = await self.tmdb_client.get_movie_details(tmdb_id)
            else:
                tmdb_result = await self.tmdb_client.get_tv_details(tmdb_id)
        elif search_term:
            # Search with user query
            tmdb_result = await self.tmdb_client.find_best_match(
                search_term,
                tmdb_type,
                year,
                file_info.name
            )
        
        # Build result
        pattern_result = self.pattern_extractor.extract(file_info.name)
        
        result = RecognitionResult(
            file_info=file_info,
            confidence=ConfidenceLevel.HIGH if tmdb_result else ConfidenceLevel.LOW,
            user_override=True
        )
        
        if tmdb_result:
            result.media_info = MediaInfo(
                media_type=media_type,
                title=tmdb_result.title,
                original_title=tmdb_result.original_title,
                year=tmdb_result.year,
                tmdb_id=tmdb_result.tmdb_id,
                tmdb_info=TMDBInfo(
                    tmdb_id=tmdb_result.tmdb_id,
                    title=tmdb_result.title,
                    original_title=tmdb_result.original_title,
                    year=tmdb_result.year,
                    overview=tmdb_result.overview,
                    poster_path=tmdb_result.poster_path,
                    genre_ids=tmdb_result.genre_ids,
                    origin_country=tmdb_result.origin_country,
                    original_language=tmdb_result.original_language
                ),
                quality=pattern_result.quality,
                source=pattern_result.source,
                codec=pattern_result.codec,
                audio=pattern_result.audio,
                release_group=pattern_result.release_group,
                season=pattern_result.season,
                episode=pattern_result.episode,
                end_episode=pattern_result.end_episode
            )
        
        # Update cache
        file_hash = self._compute_file_hash(file_info.name, file_info.size)
        await self._cache_result(
            db, file_hash, file_info.name, file_info.size, result
        )
        
        return result
    
    async def search_tmdb(
        self,
        query: str,
        media_type: MediaType,
        year: Optional[int] = None
    ) -> List[TMDBResult]:
        """
        Search TMDB for manual re-identification.
        
        Args:
            query: Search query
            media_type: Media type
            year: Optional year filter
            
        Returns:
            List of TMDB results
        """
        tmdb_type = "movie" if media_type == MediaType.MOVIE else "tv"
        results, _ = await self.tmdb_client.search_with_languages(
            query, tmdb_type, year
        )
        return results
    
    def _build_search_query(
        self,
        llm_result: ExtractedMediaInfo,
        filename: str
    ) -> str:
        """Build search query from LLM result or filename"""
        # Prefer Chinese title for better matching
        if llm_result.title_cn:
            return llm_result.title_cn
        
        if llm_result.title_en:
            return llm_result.title_en
        
        # Fallback: clean filename
        return self.pattern_extractor.clean_filename_for_search(filename)
    
    def _build_recognition_result(
        self,
        file_info: FileInfo,
        llm_result: ExtractedMediaInfo,
        tmdb_result: Optional[TMDBResult],
        pattern_result: Any,
        media_type: MediaType
    ) -> RecognitionResult:
        """Build RecognitionResult from components"""
        # Determine confidence
        if tmdb_result:
            confidence_str = tmdb_result.match_confidence
            confidence = (
                ConfidenceLevel.HIGH if confidence_str == "high" else
                ConfidenceLevel.MEDIUM if confidence_str == "medium" else
                ConfidenceLevel.LOW
            )
        else:
            confidence = ConfidenceLevel.LOW
        
        result = RecognitionResult(
            file_info=file_info,
            confidence=confidence,
            llm_extracted={
                "title_cn": llm_result.title_cn,
                "title_en": llm_result.title_en,
                "year": llm_result.year,
                "season": llm_result.season,
                "episode": llm_result.episode
            }
        )
        
        if tmdb_result:
            # Merge season/episode from LLM and pattern extraction
            season = llm_result.season or pattern_result.season
            episode = llm_result.episode or pattern_result.episode
            end_episode = llm_result.end_episode or pattern_result.end_episode
            
            result.media_info = MediaInfo(
                media_type=media_type,
                title=tmdb_result.title,
                original_title=tmdb_result.original_title,
                year=tmdb_result.year,
                tmdb_id=tmdb_result.tmdb_id,
                tmdb_info=TMDBInfo(
                    tmdb_id=tmdb_result.tmdb_id,
                    title=tmdb_result.title,
                    original_title=tmdb_result.original_title,
                    year=tmdb_result.year,
                    overview=tmdb_result.overview,
                    poster_path=tmdb_result.poster_path,
                    backdrop_path=tmdb_result.backdrop_path,
                    genre_ids=tmdb_result.genre_ids,
                    origin_country=tmdb_result.origin_country,
                    original_language=tmdb_result.original_language,
                    seasons=tmdb_result.seasons
                ),
                season=season,
                episode=episode,
                end_episode=end_episode,
                quality=pattern_result.quality,
                source=pattern_result.source,
                codec=pattern_result.codec,
                audio=pattern_result.audio,
                release_group=pattern_result.release_group
            )
        
        return result
    
    def _compute_file_hash(self, filename: str, size: int) -> str:
        """Compute hash for cache key"""
        content = f"{filename}:{size}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    async def _get_cached_result(
        self,
        db: AsyncSession,
        file_hash: str
    ) -> Optional[RecognitionCacheDB]:
        """Get cached recognition result"""
        result = await db.execute(
            select(RecognitionCacheDB).where(
                RecognitionCacheDB.file_hash == file_hash
            )
        )
        return result.scalar_one_or_none()
    
    async def _cache_result(
        self,
        db: AsyncSession,
        file_hash: str,
        filename: str,
        file_size: int,
        result: RecognitionResult
    ) -> None:
        """Cache recognition result"""
        # Check if already cached
        existing = await self._get_cached_result(db, file_hash)
        
        cache_data = {
            "media_info": result.media_info.model_dump() if result.media_info else None,
            "llm_extracted": result.llm_extracted,
            "user_override": result.user_override
        }
        
        if existing:
            # Update existing
            existing.recognition_data = cache_data
            existing.confidence = result.confidence.value
            if result.media_info:
                existing.media_type = result.media_info.media_type.value
                existing.tmdb_id = str(result.media_info.tmdb_id) if result.media_info.tmdb_id else None
        else:
            # Create new
            cache_entry = RecognitionCacheDB(
                file_hash=file_hash,
                file_name=filename,
                file_size=file_size,
                media_type=result.media_info.media_type.value if result.media_info else "unknown",
                tmdb_id=str(result.media_info.tmdb_id) if result.media_info and result.media_info.tmdb_id else None,
                recognition_data=cache_data,
                confidence=result.confidence.value
            )
            db.add(cache_entry)
        
        await db.commit()
    
    def _cached_to_result(
        self,
        file_info: FileInfo,
        cached: RecognitionCacheDB
    ) -> RecognitionResult:
        """Convert cached data to RecognitionResult"""
        data = cached.recognition_data or {}
        media_info_data = data.get("media_info")
        
        result = RecognitionResult(
            file_info=file_info,
            confidence=ConfidenceLevel(cached.confidence),
            llm_extracted=data.get("llm_extracted"),
            user_override=data.get("user_override", False)
        )
        
        if media_info_data:
            # Reconstruct MediaInfo
            media_info_data["media_type"] = MediaType(media_info_data["media_type"])
            if media_info_data.get("tmdb_info"):
                media_info_data["tmdb_info"] = TMDBInfo(**media_info_data["tmdb_info"])
            result.media_info = MediaInfo(**media_info_data)
        
        return result
    
    async def close(self):
        """Clean up resources"""
        await self.tmdb_client.close()

