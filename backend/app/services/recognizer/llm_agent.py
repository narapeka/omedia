"""
LLM Agent for media information extraction
Supports OpenAI-compatible APIs including OpenAI, Gemini, Grok, etc.
"""

import json
import logging
import time
import asyncio
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

from openai import AsyncOpenAI

from ...core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ExtractedMediaInfo:
    """Extracted media information from LLM"""
    filename: str
    title_cn: Optional[str] = None  # Chinese title
    title_en: Optional[str] = None  # English title
    year: Optional[int] = None
    tmdb_id: Optional[int] = None  # If present in filename
    # TV specific
    season: Optional[int] = None
    episode: Optional[int] = None
    end_episode: Optional[int] = None  # For multi-episode files
    # Quality info
    quality: Optional[str] = None  # 1080p, 4K, etc.
    source: Optional[str] = None  # BluRay, WEB-DL, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# System prompt for media extraction
SYSTEM_PROMPT = """You are a media file analyzer. Extract information from video filenames.

For each filename, extract:
- title_cn: Chinese title if present (use original Chinese characters)
- title_en: English title if present
- year: Release year (4-digit number, e.g., 2023)
- tmdb_id: TMDB ID if present in filename (e.g., from {tmdb-12345})
- season: Season number for TV shows (1, 2, 3, etc.)
- episode: Episode number (1, 2, 3, etc.)
- end_episode: End episode for multi-episode files (e.g., E01-E03 has episode=1, end_episode=3)
- quality: Video quality (e.g., 1080p, 720p, 4K, 2160p)
- source: Video source (e.g., BluRay, WEB-DL, HDTV, DVDRip)

Return ONLY a JSON array with extracted info for each filename.
Use null for fields you cannot determine.
Do not include explanations, only the JSON array."""

USER_PROMPT_TEMPLATE = """Extract media information from these filenames:

{filenames}

Return a JSON array with one object per filename, in the same order as input."""


class LLMAgent:
    """LLM agent for extracting media information from filenames"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: Optional[int] = None,
        rate_limit: Optional[int] = None
    ):
        """
        Initialize LLM agent.
        
        Args:
            api_key: OpenAI-compatible API key
            base_url: Custom API base URL (None for OpenAI default)
            model: Model name (e.g., gpt-4o-mini, gemini-pro)
            batch_size: Max files per request
            rate_limit: Max requests per second
        """
        self.api_key = api_key or settings.llm.api_key
        self.base_url = base_url or settings.llm.base_url
        self.model = model or settings.llm.model
        self.batch_size = batch_size or settings.llm.batch_size
        self.rate_limit = rate_limit or settings.llm.rate_limit
        
        self._min_interval = 1.0 / self.rate_limit
        self._last_request_time = 0.0
        
        # Initialize client
        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        
        self._client = AsyncOpenAI(**client_kwargs)
        
        logger.info(f"LLM Agent initialized with model: {self.model}")
    
    async def _wait_for_rate_limit(self):
        """Enforce rate limiting"""
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        
        self._last_request_time = time.time()
    
    def _parse_response(
        self,
        response_text: str,
        filenames: List[str]
    ) -> List[ExtractedMediaInfo]:
        """Parse LLM response into ExtractedMediaInfo objects"""
        results = []
        
        try:
            # Extract JSON from response
            text = response_text.strip()
            start_idx = text.find('[')
            end_idx = text.rfind(']') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON array found")
            
            json_text = text[start_idx:end_idx]
            parsed_data = json.loads(json_text)
            
            # Map results to filenames
            filename_map = {name: None for name in filenames}
            
            for i, item in enumerate(parsed_data):
                if not isinstance(item, dict):
                    continue
                
                # Get filename - try different keys
                filename = item.get('filename') or (
                    filenames[i] if i < len(filenames) else None
                )
                
                if not filename or filename not in filename_map:
                    continue
                
                # Extract and convert fields
                info = ExtractedMediaInfo(
                    filename=filename,
                    title_cn=item.get('title_cn') or item.get('cn_name'),
                    title_en=item.get('title_en') or item.get('en_name'),
                    year=self._parse_int(item.get('year')),
                    tmdb_id=self._parse_int(item.get('tmdb_id') or item.get('tmdbid')),
                    season=self._parse_int(item.get('season')),
                    episode=self._parse_int(item.get('episode')),
                    end_episode=self._parse_int(item.get('end_episode')),
                    quality=item.get('quality'),
                    source=item.get('source')
                )
                
                results.append(info)
                filename_map[filename] = info
            
            # Add empty results for missing filenames
            for filename, info in filename_map.items():
                if info is None:
                    results.append(ExtractedMediaInfo(filename=filename))
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response text: {response_text}")
            results = [ExtractedMediaInfo(filename=name) for name in filenames]
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            results = [ExtractedMediaInfo(filename=name) for name in filenames]
        
        return results
    
    def _parse_int(self, value: Any) -> Optional[int]:
        """Parse value to int, returning None on failure"""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None
    
    async def extract(
        self,
        filenames: List[str],
        media_type: str = "unknown"
    ) -> List[ExtractedMediaInfo]:
        """
        Extract media information from filenames.
        
        Args:
            filenames: List of filenames to process
            media_type: Hint for media type (movie, tv, unknown)
            
        Returns:
            List of ExtractedMediaInfo objects
        """
        if not filenames:
            return []
        
        if not self.api_key:
            logger.warning("LLM API key not configured, returning empty results")
            return [ExtractedMediaInfo(filename=name) for name in filenames]
        
        logger.info(f"Extracting info for {len(filenames)} files using {self.model}")
        
        all_results = []
        
        # Process in batches
        for i in range(0, len(filenames), self.batch_size):
            batch = filenames[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            total_batches = (len(filenames) + self.batch_size - 1) // self.batch_size
            
            logger.debug(f"Processing batch {batch_num}/{total_batches} ({len(batch)} files)")
            
            try:
                await self._wait_for_rate_limit()
                
                # Create prompt
                filenames_json = json.dumps(batch, ensure_ascii=False, indent=2)
                user_prompt = USER_PROMPT_TEMPLATE.format(filenames=filenames_json)
                
                # Add media type hint to system prompt if specified
                system_prompt = SYSTEM_PROMPT
                if media_type == "movie":
                    system_prompt += "\n\nThese are MOVIE filenames. Season/episode fields should be null."
                elif media_type == "tv":
                    system_prompt += "\n\nThese are TV SHOW filenames. Look for season/episode patterns."
                
                # Call LLM
                response = await self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1
                )
                
                response_text = response.choices[0].message.content
                batch_results = self._parse_response(response_text, batch)
                all_results.extend(batch_results)
                
                logger.debug(f"Processed batch {batch_num}/{total_batches}")
                
            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {e}")
                all_results.extend([
                    ExtractedMediaInfo(filename=name) for name in batch
                ])
        
        # Ensure results match input order
        result_map = {r.filename: r for r in all_results}
        ordered_results = [
            result_map.get(name, ExtractedMediaInfo(filename=name))
            for name in filenames
        ]
        
        logger.info(f"Extracted info for {len(ordered_results)} files")
        return ordered_results
    
    async def extract_single(
        self,
        filename: str,
        media_type: str = "unknown"
    ) -> ExtractedMediaInfo:
        """
        Extract info for a single filename.
        Convenience wrapper for extract().
        """
        results = await self.extract([filename], media_type)
        return results[0] if results else ExtractedMediaInfo(filename=filename)

