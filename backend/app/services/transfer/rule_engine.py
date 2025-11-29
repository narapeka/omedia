"""
Transfer Rule Matching Engine
Matches recognition results against configured transfer rules.
"""

import re
import logging
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...models.schemas import (
    RecognitionResult, TransferRule, RuleCondition, StorageType, MediaType
)
from ...models.db_models import TransferRuleDB

logger = logging.getLogger(__name__)


# Genre ID to name mapping (TMDB)
GENRE_MAP = {
    # TV genres
    10759: "Action & Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    10762: "Kids",
    9648: "Mystery",
    10763: "News",
    10764: "Reality",
    10765: "Sci-Fi & Fantasy",
    10766: "Soap",
    10767: "Talk",
    10768: "War & Politics",
    37: "Western",
    # Movie genres
    28: "Action",
    12: "Adventure",
    14: "Fantasy",
    36: "History",
    27: "Horror",
    10402: "Music",
    10749: "Romance",
    878: "Science Fiction",
    10770: "TV Movie",
    53: "Thriller",
    10752: "War",
}


class RuleMatchingEngine:
    """Engine for matching recognition results to transfer rules"""
    
    def __init__(self):
        pass
    
    async def match_rule(
        self,
        result: RecognitionResult,
        storage_type: StorageType,
        db: AsyncSession
    ) -> Optional[TransferRule]:
        """
        Find the best matching rule for a recognition result.
        
        Rules are evaluated in priority order (lowest number first).
        All conditions in a rule must match for the rule to apply.
        Rules are filtered by storage_type to enforce same-storage-only transfers.
        
        Args:
            result: Recognition result to match
            storage_type: Source storage type
            db: Database session
            
        Returns:
            Matching TransferRule or None
        """
        if not result.media_info:
            return None
        
        media_type = result.media_info.media_type
        
        # Query applicable rules
        query = select(TransferRuleDB).where(
            TransferRuleDB.enabled == True
        ).where(
            (TransferRuleDB.media_type == media_type.value) |
            (TransferRuleDB.media_type == "all")
        ).where(
            (TransferRuleDB.storage_type == storage_type.value) |
            (TransferRuleDB.storage_type == "all")
        ).order_by(TransferRuleDB.priority)
        
        db_result = await db.execute(query)
        rules = db_result.scalars().all()
        
        # Evaluate each rule
        for rule_db in rules:
            rule = self._db_to_schema(rule_db)
            
            if self._evaluate_rule(rule, result):
                logger.debug(f"Matched rule: {rule.name} for {result.file_info.name}")
                return rule
        
        return None
    
    def _db_to_schema(self, db_rule: TransferRuleDB) -> TransferRule:
        """Convert database rule to schema"""
        conditions = []
        for cond_data in db_rule.conditions or []:
            conditions.append(RuleCondition(
                field=cond_data.get("field", ""),
                operator=cond_data.get("operator", ""),
                value=cond_data.get("value")
            ))
        
        return TransferRule(
            id=db_rule.id,
            name=db_rule.name,
            priority=db_rule.priority,
            media_type=db_rule.media_type,
            storage_type=db_rule.storage_type,
            conditions=conditions,
            target_path=db_rule.target_path,
            naming_pattern=db_rule.naming_pattern,
            enabled=db_rule.enabled
        )
    
    def _evaluate_rule(
        self,
        rule: TransferRule,
        result: RecognitionResult
    ) -> bool:
        """
        Evaluate if a rule matches a recognition result.
        All conditions must match (AND logic).
        """
        if not rule.conditions:
            # No conditions = matches everything
            return True
        
        for condition in rule.conditions:
            if not self._evaluate_condition(condition, result):
                return False
        
        return True
    
    def _evaluate_condition(
        self,
        condition: RuleCondition,
        result: RecognitionResult
    ) -> bool:
        """Evaluate a single condition"""
        field = condition.field
        operator = condition.operator
        value = condition.value
        
        # Get field value from result
        field_value = self._get_field_value(field, result)
        
        if field_value is None:
            return False
        
        # Evaluate based on operator
        if operator == "equals":
            return self._equals(field_value, value)
        elif operator == "contains":
            return self._contains(field_value, value)
        elif operator == "in":
            return self._in_list(field_value, value)
        elif operator == "matches":
            return self._matches(field_value, value)
        elif operator == "between":
            return self._between(field_value, value)
        elif operator == "gte":
            return self._gte(field_value, value)
        elif operator == "lte":
            return self._lte(field_value, value)
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False
    
    def _get_field_value(
        self,
        field: str,
        result: RecognitionResult
    ) -> Any:
        """Get field value from recognition result"""
        media_info = result.media_info
        tmdb_info = media_info.tmdb_info if media_info else None
        
        if field == "genre":
            if tmdb_info and tmdb_info.genre_ids:
                # Convert genre IDs to names
                return [GENRE_MAP.get(gid, str(gid)) for gid in tmdb_info.genre_ids]
            return []
        
        elif field == "country":
            if tmdb_info and tmdb_info.origin_country:
                return tmdb_info.origin_country
            return []
        
        elif field == "language":
            if tmdb_info:
                return tmdb_info.original_language
            return None
        
        elif field == "year" or field == "year_range":
            if media_info:
                return media_info.year
            return None
        
        elif field == "keyword":
            # Check filename for keywords
            return result.file_info.name
        
        elif field == "network":
            # Network info would come from TMDB details (for TV)
            # Not implemented in basic TMDB response
            return None
        
        elif field == "rating":
            # TMDB rating - not in basic response
            return None
        
        return None
    
    def _equals(self, field_value: Any, expected: Any) -> bool:
        """Check equality"""
        if isinstance(field_value, str):
            return field_value.lower() == str(expected).lower()
        return field_value == expected
    
    def _contains(self, field_value: Any, search: Any) -> bool:
        """Check if field contains value"""
        search_str = str(search).lower()
        
        if isinstance(field_value, list):
            return any(search_str in str(v).lower() for v in field_value)
        
        if isinstance(field_value, str):
            return search_str in field_value.lower()
        
        return False
    
    def _in_list(self, field_value: Any, allowed: Any) -> bool:
        """Check if field value is in allowed list"""
        if not isinstance(allowed, list):
            allowed = [allowed]
        
        allowed_lower = [str(a).lower() for a in allowed]
        
        if isinstance(field_value, list):
            return any(str(v).lower() in allowed_lower for v in field_value)
        
        return str(field_value).lower() in allowed_lower
    
    def _matches(self, field_value: Any, pattern: Any) -> bool:
        """Check if field matches regex pattern"""
        try:
            if isinstance(field_value, list):
                return any(
                    re.search(str(pattern), str(v), re.IGNORECASE)
                    for v in field_value
                )
            return bool(re.search(str(pattern), str(field_value), re.IGNORECASE))
        except re.error:
            logger.warning(f"Invalid regex pattern: {pattern}")
            return False
    
    def _between(self, field_value: Any, range_val: Any) -> bool:
        """Check if field is between two values"""
        if not isinstance(range_val, (list, tuple)) or len(range_val) != 2:
            return False
        
        try:
            val = float(field_value)
            low = float(range_val[0])
            high = float(range_val[1])
            return low <= val <= high
        except (ValueError, TypeError):
            return False
    
    def _gte(self, field_value: Any, threshold: Any) -> bool:
        """Check if field >= threshold"""
        try:
            return float(field_value) >= float(threshold)
        except (ValueError, TypeError):
            return False
    
    def _lte(self, field_value: Any, threshold: Any) -> bool:
        """Check if field <= threshold"""
        try:
            return float(field_value) <= float(threshold)
        except (ValueError, TypeError):
            return False

