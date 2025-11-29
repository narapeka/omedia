"""
Transfer Service
Handles file transfer operations with rule matching and naming.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import PurePosixPath

from sqlalchemy.ext.asyncio import AsyncSession

from .rule_engine import RuleMatchingEngine
from .naming_service import NamingService
from ...models.schemas import (
    RecognitionResult, TransferRule, TransferTask, TransferStatus,
    StorageType, MediaType, DryRunReport
)
from ...models.db_models import TransferHistoryDB
from ...vfs import get_vfs_adapter, VFSError
from ...core.events import event_bus, EventType
from ...core.config import settings

logger = logging.getLogger(__name__)


class TransferService:
    """Service for transferring media files"""
    
    def __init__(self):
        self.rule_engine = RuleMatchingEngine()
        self.naming_service = NamingService()
    
    async def create_dry_run_report(
        self,
        results: List[RecognitionResult],
        storage_type: StorageType,
        db: AsyncSession
    ) -> DryRunReport:
        """
        Create a dry-run report showing what would be transferred.
        
        Args:
            results: List of recognition results
            storage_type: Source storage type
            db: Database session
            
        Returns:
            DryRunReport with matched rules and target paths
        """
        processed_results = []
        errors = []
        
        high_count = 0
        medium_count = 0
        low_count = 0
        
        for result in results:
            try:
                # Match rule
                rule = await self.rule_engine.match_rule(result, storage_type, db)
                
                if rule:
                    result.matched_rule_id = rule.id
                    result.matched_rule_name = rule.name
                    
                    # Generate target path
                    target_path = self._substitute_path_template(
                        rule.target_path,
                        result
                    )
                    
                    # Generate normalized names
                    names = self.naming_service.generate_names(
                        result,
                        pattern_name=rule.naming_pattern
                    )
                    
                    result.target_path = target_path
                    result.target_folder_name = names.get("folder_name")
                    result.target_file_name = names.get("file_name")
                
                # Count confidence levels
                confidence = result.confidence.value
                if confidence == "high":
                    high_count += 1
                elif confidence == "medium":
                    medium_count += 1
                else:
                    low_count += 1
                
                processed_results.append(result)
                
            except Exception as e:
                logger.error(f"Error processing {result.file_info.name}: {e}")
                errors.append({
                    "file": result.file_info.name,
                    "error": str(e)
                })
        
        return DryRunReport(
            total_items=len(results),
            recognized_items=len([r for r in processed_results if r.media_info]),
            high_confidence=high_count,
            medium_confidence=medium_count,
            low_confidence=low_count,
            items=processed_results,
            errors=errors
        )
    
    async def execute_transfer(
        self,
        items: List[RecognitionResult],
        storage_type: StorageType,
        db: AsyncSession,
        global_rule_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute file transfers.
        
        Args:
            items: List of recognition results to transfer
            storage_type: Storage type
            db: Database session
            global_rule_override: Optional rule ID to apply to all items
            
        Returns:
            Dictionary with transfer results
        """
        await event_bus.emit(
            EventType.TRANSFER_STARTED,
            {"item_count": len(items)}
        )
        
        success_count = 0
        failed_count = 0
        errors = []
        
        # Get VFS adapter
        adapter = get_vfs_adapter(storage_type)
        
        for item in items:
            try:
                # Get rule
                if global_rule_override:
                    # Load rule by ID
                    from ...models.db_models import TransferRuleDB
                    from sqlalchemy import select
                    
                    result = await db.execute(
                        select(TransferRuleDB).where(TransferRuleDB.id == global_rule_override)
                    )
                    rule_db = result.scalar_one_or_none()
                    
                    if rule_db:
                        item.matched_rule_id = rule_db.id
                        item.matched_rule_name = rule_db.name
                        item.target_path = self._substitute_path_template(
                            rule_db.target_path,
                            item
                        )
                
                if not item.target_path:
                    raise ValueError("No target path determined")
                
                # Generate full target path with file name
                names = self.naming_service.generate_names(item)
                target_file_path = self._build_full_target_path(
                    item.target_path,
                    names,
                    item.media_info.media_type if item.media_info else MediaType.UNKNOWN
                )
                
                # Execute transfer
                source_path = item.file_info.path
                
                # Ensure target directory exists
                target_dir = str(PurePosixPath(target_file_path).parent)
                await adapter.mkdir(target_dir, parents=True)
                
                # Move file (default: overwrite)
                await adapter.move(source_path, target_file_path, overwrite=True)
                
                # Record in history
                await self._record_transfer(
                    db,
                    item,
                    source_path,
                    target_file_path,
                    storage_type,
                    TransferStatus.COMPLETED
                )
                
                success_count += 1
                
                await event_bus.emit(
                    EventType.TRANSFER_PROGRESS,
                    {
                        "current": success_count + failed_count,
                        "total": len(items),
                        "file": item.file_info.name
                    }
                )
                
            except Exception as e:
                logger.error(f"Transfer failed for {item.file_info.name}: {e}")
                failed_count += 1
                errors.append({
                    "file": item.file_info.name,
                    "error": str(e)
                })
                
                # Record failure
                await self._record_transfer(
                    db,
                    item,
                    item.file_info.path,
                    item.target_path or "",
                    storage_type,
                    TransferStatus.FAILED,
                    str(e)
                )
        
        await event_bus.emit(
            EventType.TRANSFER_COMPLETED,
            {
                "success_count": success_count,
                "failed_count": failed_count
            }
        )
        
        return {
            "success": failed_count == 0,
            "transferred_count": success_count,
            "failed_count": failed_count,
            "errors": errors
        }
    
    async def transfer_tv_series(
        self,
        items: List[RecognitionResult],
        storage_type: StorageType,
        db: AsyncSession,
        target_base_path: str
    ) -> Dict[str, Any]:
        """
        Transfer TV series with season-by-season handling.
        Implements the logic from azf.py - seasons are moved individually
        and will overwrite existing season folders.
        
        Args:
            items: List of episode recognition results
            storage_type: Storage type
            db: Database session
            target_base_path: Base path for the show folder
            
        Returns:
            Transfer results
        """
        if not items:
            return {"success": True, "transferred_count": 0, "failed_count": 0, "errors": []}
        
        adapter = get_vfs_adapter(storage_type)
        
        # Group items by season
        seasons: Dict[int, List[RecognitionResult]] = {}
        for item in items:
            season = item.media_info.season if item.media_info else 1
            if season not in seasons:
                seasons[season] = []
            seasons[season].append(item)
        
        success_count = 0
        failed_count = 0
        errors = []
        
        # Process each season
        for season_num, season_items in seasons.items():
            try:
                # Generate season folder name
                names = self.naming_service.generate_names(season_items[0])
                season_folder = names.get("season_folder", f"Season {season_num:02d}")
                season_path = str(PurePosixPath(target_base_path) / names["folder_name"] / season_folder)
                
                # Check if season folder exists
                if await adapter.exists(season_path):
                    # Remove existing season folder (overwrite behavior)
                    logger.info(f"Removing existing season folder: {season_path}")
                    await adapter.delete(season_path, recursive=True)
                
                # Create season folder
                await adapter.mkdir(season_path, parents=True)
                
                # Transfer each episode
                for item in season_items:
                    try:
                        ep_names = self.naming_service.generate_names(item)
                        target_file_path = str(PurePosixPath(season_path) / ep_names["file_name"])
                        
                        await adapter.move(item.file_info.path, target_file_path, overwrite=True)
                        
                        await self._record_transfer(
                            db, item, item.file_info.path, target_file_path,
                            storage_type, TransferStatus.COMPLETED
                        )
                        success_count += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to transfer episode: {e}")
                        failed_count += 1
                        errors.append({"file": item.file_info.name, "error": str(e)})
                
            except Exception as e:
                logger.error(f"Failed to process season {season_num}: {e}")
                failed_count += len(season_items)
                for item in season_items:
                    errors.append({"file": item.file_info.name, "error": str(e)})
        
        return {
            "success": failed_count == 0,
            "transferred_count": success_count,
            "failed_count": failed_count,
            "errors": errors
        }
    
    def _substitute_path_template(
        self,
        template: str,
        result: RecognitionResult
    ) -> str:
        """Substitute variables in path template"""
        if not result.media_info:
            return template
        
        media_info = result.media_info
        
        # Build substitution map
        subs = {
            "{title}": media_info.title or "Unknown",
            "{year}": str(media_info.year or "Unknown"),
            "{tmdb_id}": str(media_info.tmdb_id or "0"),
            "{quality}": media_info.quality or "",
            "{season}": f"{media_info.season:02d}" if media_info.season else "",
        }
        
        path = template
        for key, value in subs.items():
            path = path.replace(key, value)
        
        return path
    
    def _build_full_target_path(
        self,
        base_path: str,
        names: Dict[str, str],
        media_type: MediaType
    ) -> str:
        """Build full target path including folder and file name"""
        parts = [base_path]
        
        if names.get("folder_name"):
            parts.append(names["folder_name"])
        
        if media_type == MediaType.TV and names.get("season_folder"):
            parts.append(names["season_folder"])
        
        parts.append(names.get("file_name", "unknown"))
        
        return str(PurePosixPath(*parts))
    
    async def _record_transfer(
        self,
        db: AsyncSession,
        item: RecognitionResult,
        source_path: str,
        target_path: str,
        storage_type: StorageType,
        status: TransferStatus,
        error_message: Optional[str] = None
    ) -> None:
        """Record transfer in history"""
        history = TransferHistoryDB(
            source_path=source_path,
            target_path=target_path,
            storage_type=storage_type.value,
            media_type=item.media_info.media_type.value if item.media_info else "unknown",
            media_title=item.media_info.title if item.media_info else None,
            tmdb_id=str(item.media_info.tmdb_id) if item.media_info and item.media_info.tmdb_id else None,
            matched_rule_id=item.matched_rule_id,
            status=status.value,
            error_message=error_message,
            user_override=item.user_override,
            file_size=item.file_info.size,
            completed_at=datetime.utcnow() if status == TransferStatus.COMPLETED else None
        )
        
        db.add(history)
        await db.commit()

