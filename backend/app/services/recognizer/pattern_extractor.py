"""
Pattern Extractor for media filenames
Extracts season/episode numbers, quality, and other metadata using regex patterns.
"""

import re
import logging
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Chinese numeral to integer mapping
CHINESE_NUMERALS = {
    '零': 0, '〇': 0, '一': 1, '壹': 1, '二': 2, '贰': 2, '两': 2,
    '三': 3, '叁': 3, '四': 4, '肆': 4, '五': 5, '伍': 5,
    '六': 6, '陆': 6, '七': 7, '柒': 7, '八': 8, '捌': 8,
    '九': 9, '玖': 9, '十': 10, '拾': 10,
    '百': 100, '佰': 100
}


@dataclass
class PatternResult:
    """Result of pattern extraction"""
    season: Optional[int] = None
    episode: Optional[int] = None
    end_episode: Optional[int] = None
    quality: Optional[str] = None
    source: Optional[str] = None
    codec: Optional[str] = None
    audio: Optional[str] = None
    year: Optional[int] = None
    release_group: Optional[str] = None


class PatternExtractor:
    """Extract metadata from media filenames using patterns"""
    
    # Season patterns
    SEASON_PATTERNS = [
        r'[Ss](?:eason\s*)?(\d+)',  # S01, Season 1, season01
        r'第([一二三四五六七八九十壹贰叁肆伍陆柒捌玖拾\d]+)季',  # 第三季, 第1季
        r'([一二三四五六七八九十壹贰叁肆伍陆柒捌玖拾]+)季',  # 三季
    ]
    
    # Episode patterns
    EPISODE_PATTERNS = [
        r'[Ss](\d+)[Ee][Pp]?(\d+)',  # S01E01, S01EP01
        r'[Ss](\d+)\.?[Ee](\d+)',  # S01.E01
        r'(\d+)[xX](\d+)',  # 1x01
        r'第([一二三四五六七八九十壹贰叁肆伍陆柒捌玖拾\d]+)集',  # 第六集
        r'[Ee][Pp]?(\d+)',  # E01, EP01
        r'(?:^|[^\d])(\d{1,3})(?:[^\d]|$)',  # Standalone numbers
    ]
    
    # Multi-episode patterns
    MULTI_EPISODE_PATTERNS = [
        r'[Ss](\d+)[Ee](\d+)-[Ee]?(\d+)',  # S01E01-E02, S01E01-02
        r'[Ee][Pp]?(\d+)-[Ee]?[Pp]?(\d+)',  # E01-E02, EP01-EP02
    ]
    
    # Quality patterns
    QUALITY_PATTERNS = [
        (r'\b(2160[pi]?|4[Kk]|UHD)\b', '2160p'),
        (r'\b(1080[pi]?)\b', '1080p'),
        (r'\b(720[pi]?)\b', '720p'),
        (r'\b(480[pi]?)\b', '480p'),
        (r'\b(576[pi]?)\b', '576p'),
    ]
    
    # Source patterns
    SOURCE_PATTERNS = [
        (r'\b(WEB-DL|WEBDL)\b', 'WEB-DL'),
        (r'\b(WEBRip)\b', 'WEBRip'),
        (r'\b(BluRay|Blu-Ray|BDRip|BRRip)\b', 'BluRay'),
        (r'\b(HDTV)\b', 'HDTV'),
        (r'\b(DVDRip|DVD)\b', 'DVDRip'),
        (r'\b(Remux)\b', 'Remux'),
    ]
    
    # Codec patterns
    CODEC_PATTERNS = [
        (r'\b(HEVC|[Hh]\.?265|[Xx]265)\b', 'HEVC'),
        (r'\b(AVC|[Hh]\.?264|[Xx]264)\b', 'AVC'),
        (r'\b(VP9)\b', 'VP9'),
        (r'\b(AV1)\b', 'AV1'),
    ]
    
    # Audio patterns
    AUDIO_PATTERNS = [
        (r'\b(Atmos)\b', 'Atmos'),
        (r'\b(TrueHD)\b', 'TrueHD'),
        (r'\b(DTS-HD(?:\s*MA)?|DTSHD(?:MA)?)\b', 'DTS-HD MA'),
        (r'\b(DTS)\b', 'DTS'),
        (r'\b(DD[P\+]?5\.1|DDP?5\.1)\b', 'DD+5.1'),
        (r'\b(AAC)\b', 'AAC'),
        (r'\b(FLAC)\b', 'FLAC'),
    ]
    
    # Metadata to remove before processing
    REMOVE_PATTERNS = [
        r'\b(?:1080|720|576|480|360|240|2160|1440|4320)[pi]?\b',
        r'\b(?:[HhXx]\.?26[45]|HEVC|AVC)\b',
        r'\b(?:WEB-DL|WEBRip|BluRay|HDTV|DVDRip|Remux)\b',
        r'\b(?:AAC|AC3|DTS|FLAC|TrueHD|Atmos)\b',
        r'\b\d+\.\d+\s*(?:GB|MB)\b',
    ]
    
    def __init__(self):
        pass
    
    def extract(self, filename: str) -> PatternResult:
        """
        Extract all metadata from filename.
        
        Args:
            filename: Media filename
            
        Returns:
            PatternResult with extracted metadata
        """
        result = PatternResult()
        
        # Extract quality
        for pattern, value in self.QUALITY_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                result.quality = value
                break
        
        # Extract source
        for pattern, value in self.SOURCE_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                result.source = value
                break
        
        # Extract codec
        for pattern, value in self.CODEC_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                result.codec = value
                break
        
        # Extract audio
        for pattern, value in self.AUDIO_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                result.audio = value
                break
        
        # Extract year (4-digit number between 1900-2099)
        year_match = re.search(r'\b((?:19|20)\d{2})\b', filename)
        if year_match:
            result.year = int(year_match.group(1))
        
        # Extract release group (typically at the end in brackets or after dash)
        group_match = re.search(r'-([A-Za-z0-9]+)(?:\.\w{2,4})?$', filename)
        if not group_match:
            group_match = re.search(r'\[([A-Za-z0-9]+)\](?:\.\w{2,4})?$', filename)
        if group_match:
            result.release_group = group_match.group(1)
        
        # Extract season and episode
        season, episode, end_episode = self.extract_episode_info(filename)
        result.season = season
        result.episode = episode
        result.end_episode = end_episode
        
        return result
    
    def extract_season_number(
        self,
        text: str,
        fallback: int = 1
    ) -> int:
        """Extract season number from text"""
        # Normalize text - remove metadata
        normalized = self._normalize_text(text)
        
        for pattern in self.SEASON_PATTERNS:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                try:
                    matched_text = match.group(1)
                    # Try Chinese numerals first
                    if re.search(r'[一二三四五六七八九十壹贰叁肆伍陆柒捌玖拾]', matched_text):
                        return self._parse_chinese_number(matched_text)
                    return int(matched_text)
                except (ValueError, TypeError):
                    continue
        
        return fallback
    
    def extract_episode_info(
        self,
        filename: str
    ) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """
        Extract season and episode numbers from filename.
        
        Returns:
            Tuple of (season, episode, end_episode)
        """
        # Normalize filename
        normalized = self._normalize_text(filename)
        
        # Check multi-episode patterns first
        for pattern in self.MULTI_EPISODE_PATTERNS:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 3:
                    # S01E01-E02 format
                    return int(groups[0]), int(groups[1]), int(groups[2])
                elif len(groups) == 2:
                    # E01-E02 format (no season)
                    return 1, int(groups[0]), int(groups[1])
        
        # Check standard season+episode patterns
        for pattern in self.EPISODE_PATTERNS[:4]:  # S##E##, ##x##, 第X集
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 2:
                        # S##E## or ##x## format
                        return int(groups[0]), int(groups[1]), None
                    elif len(groups) == 1:
                        # 第X集 format - no season
                        matched_text = groups[0]
                        if re.search(r'[一二三四五六七八九十]', matched_text):
                            ep = self._parse_chinese_number(matched_text)
                        else:
                            ep = int(matched_text)
                        return None, ep, None
                except (ValueError, TypeError):
                    continue
        
        # Check episode-only patterns (EP01, E01)
        ep_match = re.search(r'[Ee][Pp]?(\d+)', normalized)
        if ep_match:
            return None, int(ep_match.group(1)), None
        
        # Fallback: look for standalone numbers
        # Remove extension first
        name_no_ext = normalized.rsplit('.', 1)[0]
        num_match = re.search(r'(?:^|[^\d])(\d{1,3})(?:[^\d]|$)', name_no_ext)
        if num_match:
            num = int(num_match.group(1))
            # Filter out year-like numbers
            if 1 <= num <= 300:
                return None, num, None
        
        return None, None, None
    
    def _normalize_text(self, text: str) -> str:
        """Remove metadata patterns from text"""
        normalized = text
        for pattern in self.REMOVE_PATTERNS:
            normalized = re.sub(pattern, ' ', normalized, flags=re.IGNORECASE)
        # Clean up whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def _parse_chinese_number(self, text: str) -> int:
        """Parse Chinese numeral string to integer"""
        if not text:
            return 0
        
        # Pure digit
        if text.isdigit():
            return int(text)
        
        result = 0
        current = 0
        
        for char in text:
            if char in CHINESE_NUMERALS:
                val = CHINESE_NUMERALS[char]
                if val == 10:
                    if current == 0:
                        current = 1
                    result += current * 10
                    current = 0
                elif val == 100:
                    if current == 0:
                        current = 1
                    result += current * 100
                    current = 0
                else:
                    current = val
        
        return result + current
    
    def clean_filename_for_search(self, filename: str) -> str:
        """
        Clean filename for TMDB search.
        Removes quality, codec, and other metadata.
        """
        # Remove extension
        name = filename
        if '.' in name:
            parts = name.rsplit('.', 1)
            if len(parts[-1]) <= 4 and parts[-1].isalpha():
                name = parts[0]
        
        # Remove common patterns
        patterns_to_remove = [
            r'\[.*?\]',  # [anything]
            r'\(.*?\)',  # (anything)
            r'\{.*?\}',  # {anything}
            r'\b(?:1080|720|480|2160|4K|UHD)[pi]?\b',
            r'\b(?:BluRay|WEB-DL|WEBRip|HDTV|DVDRip|Remux)\b',
            r'\b(?:HEVC|[HhXx]\.?26[45]|AVC|VP9)\b',
            r'\b(?:AAC|AC3|DTS|FLAC|TrueHD|Atmos)[\d\.]*\b',
            r'\b(?:DD[P\+]?|EAC3)[\d\.]*\b',
            r'[Ss]\d+[Ee]?\d+.*$',  # Remove everything after S##E##
            r'-[A-Za-z0-9]+$',  # Release group
        ]
        
        for pattern in patterns_to_remove:
            name = re.sub(pattern, ' ', name, flags=re.IGNORECASE)
        
        # Replace separators with spaces
        name = re.sub(r'[._-]+', ' ', name)
        
        # Clean up whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name

