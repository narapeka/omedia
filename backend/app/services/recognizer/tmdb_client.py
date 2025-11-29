"""
TMDB API Client
Provides access to The Movie Database API for media metadata.
"""

import asyncio
import logging
import time
import threading
import re
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from ...core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TMDBResult:
    """TMDB search/details result"""
    tmdb_id: int
    media_type: str  # movie or tv
    title: str
    original_title: Optional[str] = None
    year: Optional[int] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    # Category fields
    genre_ids: List[int] = field(default_factory=list)
    origin_country: List[str] = field(default_factory=list)
    original_language: Optional[str] = None
    # TV specific
    seasons: Optional[List[Dict]] = None
    # Confidence tracking
    match_confidence: str = "low"  # high, medium, low
    alternative_titles: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tmdb_id": self.tmdb_id,
            "media_type": self.media_type,
            "title": self.title,
            "original_title": self.original_title,
            "year": self.year,
            "overview": self.overview,
            "poster_path": self.poster_path,
            "backdrop_path": self.backdrop_path,
            "genre_ids": self.genre_ids,
            "origin_country": self.origin_country,
            "original_language": self.original_language,
            "seasons": self.seasons,
            "match_confidence": self.match_confidence,
            "alternative_titles": self.alternative_titles,
        }


class TMDBClient:
    """Async client for TMDB API"""
    
    BASE_URL = "https://api.themoviedb.org/3"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        languages: Optional[List[str]] = None,
        rate_limit: Optional[int] = None,
        proxy_host: Optional[str] = None,
        proxy_port: Optional[int] = None
    ):
        """
        Initialize TMDB client.
        
        Args:
            api_key: TMDB API key
            languages: List of languages to try for searches
            rate_limit: Max requests per second
            proxy_host: Proxy host
            proxy_port: Proxy port
        """
        self.api_key = api_key or settings.tmdb.api_key
        self.languages = languages or settings.tmdb.languages
        self.rate_limit = rate_limit or settings.tmdb.rate_limit
        
        self._min_interval = 1.0 / self.rate_limit
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()
        
        # Configure HTTP client
        transport_kwargs = {}
        if proxy_host and proxy_port:
            proxy_url = f"http://{proxy_host}:{proxy_port}"
            transport_kwargs["proxy"] = proxy_url
        
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={"X-Forwarded-Host": "api.themoviedb.org"},
            **transport_kwargs
        )
        
        logger.info(f"TMDB Client initialized with {len(self.languages)} languages")
    
    async def _wait_for_rate_limit(self):
        """Enforce rate limiting"""
        async with self._lock:
            current_time = time.time()
            elapsed = current_time - self._last_request_time
            
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            
            self._last_request_time = time.time()
    
    async def _request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        language: Optional[str] = None
    ) -> Optional[Dict]:
        """Make API request with rate limiting and error handling"""
        await self._wait_for_rate_limit()
        
        url = f"{self.BASE_URL}{endpoint}"
        request_params = {
            "api_key": self.api_key,
            **(params or {})
        }
        
        if language:
            request_params["language"] = language
        elif self.languages:
            request_params["language"] = self.languages[0]
        
        try:
            response = await self._client.get(url, params=request_params)
            
            if response.status_code == 429:
                # Rate limited - wait and retry
                retry_after = int(response.headers.get("Retry-After", 10))
                logger.warning(f"Rate limited, waiting {retry_after}s")
                await asyncio.sleep(retry_after)
                return await self._request(endpoint, params, language)
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"TMDB API error: {e}")
            return None
        except Exception as e:
            logger.error(f"TMDB request failed: {e}")
            return None
    
    async def search_movie(
        self,
        query: str,
        year: Optional[int] = None,
        language: Optional[str] = None
    ) -> List[TMDBResult]:
        """Search for movies"""
        params = {"query": query}
        if year:
            params["year"] = year
        
        data = await self._request("/search/movie", params, language)
        if not data:
            return []
        
        results = []
        for item in data.get("results", []):
            year_val = self._extract_year(item.get("release_date"))
            results.append(TMDBResult(
                tmdb_id=item["id"],
                media_type="movie",
                title=item.get("title", ""),
                original_title=item.get("original_title"),
                year=year_val,
                overview=item.get("overview"),
                poster_path=item.get("poster_path"),
                backdrop_path=item.get("backdrop_path"),
                genre_ids=item.get("genre_ids", []),
                original_language=item.get("original_language")
            ))
        
        return results
    
    async def search_tv(
        self,
        query: str,
        year: Optional[int] = None,
        language: Optional[str] = None
    ) -> List[TMDBResult]:
        """Search for TV shows"""
        params = {"query": query}
        if year:
            params["first_air_date_year"] = year
        
        data = await self._request("/search/tv", params, language)
        if not data:
            return []
        
        results = []
        for item in data.get("results", []):
            year_val = self._extract_year(item.get("first_air_date"))
            results.append(TMDBResult(
                tmdb_id=item["id"],
                media_type="tv",
                title=item.get("name", ""),
                original_title=item.get("original_name"),
                year=year_val,
                overview=item.get("overview"),
                poster_path=item.get("poster_path"),
                backdrop_path=item.get("backdrop_path"),
                genre_ids=item.get("genre_ids", []),
                origin_country=item.get("origin_country", []),
                original_language=item.get("original_language")
            ))
        
        return results
    
    async def get_movie_details(
        self,
        movie_id: int,
        language: Optional[str] = None
    ) -> Optional[TMDBResult]:
        """Get movie details by ID"""
        params = {"append_to_response": "alternative_titles"}
        data = await self._request(f"/movie/{movie_id}", params, language)
        
        if not data:
            return None
        
        year_val = self._extract_year(data.get("release_date"))
        alt_titles = self._extract_alternative_titles(data.get("alternative_titles", {}))
        
        return TMDBResult(
            tmdb_id=data["id"],
            media_type="movie",
            title=data.get("title", ""),
            original_title=data.get("original_title"),
            year=year_val,
            overview=data.get("overview"),
            poster_path=data.get("poster_path"),
            backdrop_path=data.get("backdrop_path"),
            genre_ids=[g["id"] for g in data.get("genres", [])],
            original_language=data.get("original_language"),
            match_confidence="high",  # Direct ID lookup
            alternative_titles=alt_titles
        )
    
    async def get_tv_details(
        self,
        tv_id: int,
        language: Optional[str] = None
    ) -> Optional[TMDBResult]:
        """Get TV show details by ID"""
        params = {"append_to_response": "alternative_titles"}
        data = await self._request(f"/tv/{tv_id}", params, language)
        
        if not data:
            return None
        
        year_val = self._extract_year(data.get("first_air_date"))
        alt_titles = self._extract_alternative_titles(
            data.get("alternative_titles", {}),
            is_tv=True
        )
        
        # Extract seasons info
        seasons = []
        for season in data.get("seasons", []):
            if season.get("season_number", 0) > 0:  # Skip specials
                seasons.append({
                    "season_number": season["season_number"],
                    "episode_count": season.get("episode_count", 0),
                    "air_date": season.get("air_date"),
                    "name": season.get("name")
                })
        
        return TMDBResult(
            tmdb_id=data["id"],
            media_type="tv",
            title=data.get("name", ""),
            original_title=data.get("original_name"),
            year=year_val,
            overview=data.get("overview"),
            poster_path=data.get("poster_path"),
            backdrop_path=data.get("backdrop_path"),
            genre_ids=[g["id"] for g in data.get("genres", [])],
            origin_country=data.get("origin_country", []),
            original_language=data.get("original_language"),
            seasons=seasons,
            match_confidence="high",
            alternative_titles=alt_titles
        )
    
    async def search_with_languages(
        self,
        query: str,
        media_type: str,
        year: Optional[int] = None
    ) -> Tuple[List[TMDBResult], Optional[str]]:
        """
        Search using multiple languages, return first results found.
        
        Returns:
            Tuple of (results, language_used)
        """
        search_fn = self.search_movie if media_type == "movie" else self.search_tv
        
        for lang in self.languages:
            results = await search_fn(query, year, lang)
            if results:
                return results, lang
        
        # Try without language preference
        results = await search_fn(query, year, None)
        return results, None
    
    async def find_best_match(
        self,
        query: str,
        media_type: str,
        year: Optional[int] = None,
        original_filename: Optional[str] = None
    ) -> Optional[TMDBResult]:
        """
        Find the best matching media item with confidence scoring.
        
        Args:
            query: Search query (title)
            media_type: movie or tv
            year: Optional year for filtering
            original_filename: Original filename for confidence checking
            
        Returns:
            Best matching TMDBResult with confidence level
        """
        results, lang = await self.search_with_languages(query, media_type, year)
        
        if not results:
            # Try without year
            if year:
                results, lang = await self.search_with_languages(query, media_type, None)
        
        if not results:
            return None
        
        # Get first result (TMDB typically returns best matches first)
        best = results[0]
        
        # Get full details
        if media_type == "movie":
            details = await self.get_movie_details(best.tmdb_id, lang)
        else:
            details = await self.get_tv_details(best.tmdb_id, lang)
        
        if not details:
            details = best
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            details, query, year, original_filename, len(results)
        )
        details.match_confidence = confidence
        
        return details
    
    def _calculate_confidence(
        self,
        result: TMDBResult,
        query: str,
        year: Optional[int],
        filename: Optional[str],
        total_results: int
    ) -> str:
        """Calculate match confidence"""
        score = 0
        
        # Title match
        query_lower = query.lower()
        if result.title.lower() == query_lower:
            score += 3
        elif query_lower in result.title.lower():
            score += 2
        elif result.original_title and query_lower in result.original_title.lower():
            score += 2
        elif any(query_lower in alt.lower() for alt in result.alternative_titles):
            score += 1
        
        # Year match
        if year and result.year:
            if year == result.year:
                score += 2
            elif abs(year - result.year) == 1:
                score += 1  # Off by one year is okay
        
        # Filename contains title (if provided)
        if filename:
            filename_lower = filename.lower()
            if result.title.lower() in filename_lower:
                score += 1
            if result.original_title and result.original_title.lower() in filename_lower:
                score += 1
        
        # Single result boost
        if total_results == 1:
            score += 1
        
        # Determine confidence level
        if score >= 5:
            return "high"
        elif score >= 3:
            return "medium"
        else:
            return "low"
    
    def _extract_year(self, date_str: Optional[str]) -> Optional[int]:
        """Extract year from date string (YYYY-MM-DD)"""
        if not date_str:
            return None
        try:
            return int(date_str[:4])
        except (ValueError, IndexError):
            return None
    
    def _extract_alternative_titles(
        self,
        data: Dict,
        is_tv: bool = False
    ) -> List[str]:
        """Extract alternative titles from TMDB response"""
        titles = []
        key = "results" if is_tv else "titles"
        
        for item in data.get(key, []):
            title = item.get("title")
            if title:
                titles.append(title)
        
        return titles
    
    def is_chinese(self, text: str) -> bool:
        """Check if text contains Chinese characters"""
        if not text:
            return False
        return bool(re.search(r'[\u4e00-\u9fff]', text))
    
    async def close(self):
        """Close HTTP client"""
        await self._client.aclose()

