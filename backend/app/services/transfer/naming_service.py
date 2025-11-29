"""
Naming Service
Generates normalized folder and file names based on patterns and TMDB metadata.
"""

import re
import logging
from typing import Optional, Dict, Any
from pathlib import PurePosixPath

from pypinyin import lazy_pinyin, Style

from ...models.schemas import RecognitionResult, MediaType
from ...core.config import settings

logger = logging.getLogger(__name__)


# Characters that are invalid in filenames (for different OS)
INVALID_CHARS = r'[<>:"/\\|?*]'

# Default naming patterns (Emby standard)
DEFAULT_MOVIE_FOLDER = "{title} ({year}) {{tmdb-{tmdb_id}}}"
DEFAULT_MOVIE_FILE = "{title} ({year}){version}{ext}"
DEFAULT_TV_FOLDER = "{title} ({year}) {{tmdb-{tmdb_id}}}"
DEFAULT_TV_SEASON_FOLDER = "Season {season:02d}"
DEFAULT_TV_EPISODE_FILE = "{title} - S{season:02d}E{episode:02d}{ext}"


class NamingService:
    """Service for generating normalized media names"""
    
    def __init__(self):
        self.presets = settings.naming_presets
    
    def generate_names(
        self,
        result: RecognitionResult,
        pattern_name: Optional[str] = None,
        version_tag: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate normalized folder and file names.
        
        Args:
            result: Recognition result with media info
            pattern_name: Name of preset pattern to use (default: emby_standard)
            version_tag: Optional version tag to append (e.g., "[4K]")
            
        Returns:
            Dictionary with keys: folder_name, file_name, season_folder (for TV)
        """
        if not result.media_info:
            return self._generate_fallback_names(result.file_info.name)
        
        media_info = result.media_info
        
        # Get pattern
        pattern = self._get_pattern(
            pattern_name or "emby_standard",
            media_info.media_type
        )
        
        # Build context for substitution
        context = self._build_context(result, version_tag)
        
        # Generate names
        if media_info.media_type == MediaType.MOVIE:
            return self._generate_movie_names(pattern, context)
        else:
            return self._generate_tv_names(pattern, context)
    
    def _get_pattern(
        self,
        pattern_name: str,
        media_type: MediaType
    ) -> Dict[str, str]:
        """Get naming pattern by name"""
        preset = self.presets.get(pattern_name, self.presets.get("emby_standard", {}))
        
        return {
            "movie_folder": preset.get("movie_folder", DEFAULT_MOVIE_FOLDER),
            "movie_file": preset.get("movie_file", DEFAULT_MOVIE_FILE),
            "tv_folder": preset.get("tv_folder", DEFAULT_TV_FOLDER),
            "tv_season_folder": preset.get("tv_season_folder", DEFAULT_TV_SEASON_FOLDER),
            "tv_episode_file": preset.get("tv_episode_file", DEFAULT_TV_EPISODE_FILE),
        }
    
    def _build_context(
        self,
        result: RecognitionResult,
        version_tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build substitution context from recognition result"""
        media_info = result.media_info
        file_info = result.file_info
        
        # Get file extension
        ext = file_info.extension or ""
        if not ext.startswith("."):
            ext = "." + ext if ext else ""
        
        context = {
            # Basic info
            "title": media_info.title or "Unknown",
            "original_title": media_info.original_title or media_info.title or "Unknown",
            "year": media_info.year or "Unknown",
            "tmdb_id": media_info.tmdb_id or "0",
            
            # Quality info
            "quality": media_info.quality or "",
            "source": media_info.source or "",
            "codec": media_info.codec or "",
            "audio": media_info.audio or "",
            "release_group": media_info.release_group or "",
            
            # Version tag
            "version": f" {version_tag}" if version_tag else "",
            
            # File extension
            "ext": ext,
            
            # TV specific
            "season": media_info.season or 1,
            "episode": media_info.episode or 1,
            "end_episode": media_info.end_episode,
            "episode_title": media_info.episode_title or "",
            
            # Derived fields
            "first_letter": self._get_first_letter(media_info.title or ""),
            "decade": f"{(media_info.year // 10) * 10}s" if media_info.year else "Unknown",
        }
        
        return context
    
    def _generate_movie_names(
        self,
        pattern: Dict[str, str],
        context: Dict[str, Any]
    ) -> Dict[str, str]:
        """Generate movie folder and file names"""
        folder_name = self._substitute(pattern["movie_folder"], context)
        file_name = self._substitute(pattern["movie_file"], context)
        
        return {
            "folder_name": self._clean_name(folder_name),
            "file_name": self._clean_name(file_name),
        }
    
    def _generate_tv_names(
        self,
        pattern: Dict[str, str],
        context: Dict[str, Any]
    ) -> Dict[str, str]:
        """Generate TV show folder and file names"""
        folder_name = self._substitute(pattern["tv_folder"], context)
        season_folder = self._substitute(pattern["tv_season_folder"], context)
        
        # Handle multi-episode files
        if context.get("end_episode"):
            # Format: S01E01-E03
            episode_pattern = pattern["tv_episode_file"]
            # Replace episode placeholder with range
            context["episode_range"] = f"E{context['episode']:02d}-E{context['end_episode']:02d}"
            file_name = self._substitute(
                episode_pattern.replace("E{episode:02d}", "{episode_range}"),
                context
            )
        else:
            file_name = self._substitute(pattern["tv_episode_file"], context)
        
        return {
            "folder_name": self._clean_name(folder_name),
            "season_folder": self._clean_name(season_folder),
            "file_name": self._clean_name(file_name),
        }
    
    def _substitute(self, template: str, context: Dict[str, Any]) -> str:
        """Substitute template variables"""
        result = template
        
        # Handle format specifiers like {season:02d}
        for key, value in context.items():
            # Simple substitution {key}
            result = result.replace(f"{{{key}}}", str(value) if value is not None else "")
            
            # With format specifier {key:format}
            pattern = rf"\{{{key}:([^}}]+)\}}"
            match = re.search(pattern, result)
            if match:
                fmt = match.group(1)
                try:
                    formatted = f"{{:{fmt}}}".format(value)
                    result = re.sub(pattern, formatted, result)
                except (ValueError, KeyError):
                    result = re.sub(pattern, str(value), result)
        
        return result
    
    def _clean_name(self, name: str) -> str:
        """Clean name for filesystem compatibility"""
        # Replace invalid characters with full-width equivalents or remove
        name = name.replace(":", "：")
        name = name.replace("/", "／")
        name = name.replace("\\", "＼")
        name = name.replace("?", "？")
        name = name.replace("*", "＊")
        name = name.replace("<", "＜")
        name = name.replace(">", "＞")
        name = name.replace("|", "｜")
        name = name.replace('"', "＂")
        
        # Remove multiple spaces
        name = re.sub(r"\s+", " ", name)
        
        # Trim spaces and dots from ends
        name = name.strip(" .")
        
        return name
    
    def _get_first_letter(self, title: str) -> str:
        """Get first letter for categorization (handles Chinese via pinyin)"""
        if not title:
            return "#"
        
        first_char = title[0]
        
        # Check if Chinese character
        if '\u4e00' <= first_char <= '\u9fff':
            # Get pinyin and take first letter
            pinyin = lazy_pinyin(first_char, style=Style.FIRST_LETTER)
            if pinyin:
                return pinyin[0].upper()
        
        # ASCII letter
        if first_char.isalpha():
            return first_char.upper()
        
        # Number or other
        if first_char.isdigit():
            return "#"
        
        return "#"
    
    def _generate_fallback_names(self, original_name: str) -> Dict[str, str]:
        """Generate fallback names when no media info available"""
        # Remove extension
        name = original_name
        if "." in name:
            name = name.rsplit(".", 1)[0]
        
        return {
            "folder_name": self._clean_name(name),
            "file_name": original_name,
        }
    
    def get_target_path(
        self,
        result: RecognitionResult,
        base_path: str,
        pattern_name: Optional[str] = None,
        version_tag: Optional[str] = None
    ) -> str:
        """
        Get full target path for a file.
        
        Args:
            result: Recognition result
            base_path: Base target directory
            pattern_name: Naming pattern to use
            version_tag: Optional version tag
            
        Returns:
            Full target path as string
        """
        names = self.generate_names(result, pattern_name, version_tag)
        
        path_parts = [base_path, names["folder_name"]]
        
        if result.media_info and result.media_info.media_type == MediaType.TV:
            if "season_folder" in names:
                path_parts.append(names["season_folder"])
        
        path_parts.append(names["file_name"])
        
        return str(PurePosixPath(*path_parts))

