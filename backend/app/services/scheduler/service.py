"""
Scheduler Service
Manages watchdog and life event monitoring jobs.
"""

import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .watchdog_monitor import WatchdogMonitor
from .life_event_monitor import LifeEventMonitor
from ..recognizer import RecognitionService
from ..transfer import TransferService
from ...models.schemas import (
    Job, JobStatus, StorageType, MediaType, ConfidenceLevel, FileInfo
)
from ...models.db_models import JobDB
from ...core.database import get_db_context
from ...core.events import event_bus, EventType

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Service for managing monitoring jobs.
    
    Coordinates watchdog and life event monitors with
    recognition and transfer services.
    """
    
    def __init__(self):
        self.recognition_service = RecognitionService()
        self.transfer_service = TransferService()
        
        # Initialize monitors with callbacks
        self.watchdog_monitor = WatchdogMonitor(
            on_file_detected=self._handle_detected_file
        )
        self.life_event_monitor = LifeEventMonitor(
            on_file_detected=self._handle_detected_file
        )
        
        self._pending_files: Dict[str, List[str]] = {}  # job_id -> list of paths
        self._processing_lock = asyncio.Lock()
    
    async def start(self):
        """Start the scheduler service and load enabled jobs"""
        logger.info("Starting scheduler service...")
        
        async with get_db_context() as db:
            # Load enabled jobs
            result = await db.execute(
                select(JobDB).where(
                    JobDB.enabled == True,
                    JobDB.status == JobStatus.ACTIVE.value
                )
            )
            jobs = result.scalars().all()
            
            for job in jobs:
                await self._start_job(job)
        
        logger.info(f"Scheduler service started with {len(jobs)} active jobs")
    
    async def stop(self):
        """Stop the scheduler service"""
        logger.info("Stopping scheduler service...")
        
        self.watchdog_monitor.stop_all()
        await self.life_event_monitor.stop_all()
        await self.recognition_service.close()
        
        logger.info("Scheduler service stopped")
    
    async def start_job(self, job_id: str) -> bool:
        """Start a specific job"""
        async with get_db_context() as db:
            result = await db.execute(
                select(JobDB).where(JobDB.id == job_id)
            )
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"Job not found: {job_id}")
                return False
            
            return await self._start_job(job)
    
    async def stop_job(self, job_id: str) -> bool:
        """Stop a specific job"""
        # Try watchdog first
        if self.watchdog_monitor.is_monitoring(job_id):
            return self.watchdog_monitor.stop_monitoring(job_id)
        
        # Try life event monitor
        if self.life_event_monitor.is_monitoring(job_id):
            return await self.life_event_monitor.stop_monitoring(job_id)
        
        logger.warning(f"Job {job_id} is not running")
        return False
    
    async def _start_job(self, job: JobDB) -> bool:
        """Internal method to start a job"""
        try:
            if job.job_type == "watchdog":
                return self.watchdog_monitor.start_monitoring(
                    job_id=job.id,
                    path=job.source_path,
                    poll_interval=job.poll_interval
                )
            elif job.job_type == "life_event":
                return await self.life_event_monitor.start_monitoring(
                    job_id=job.id,
                    path=job.source_path,
                    event_types=job.event_types
                )
            else:
                logger.error(f"Unknown job type: {job.job_type}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start job {job.id}: {e}")
            return False
    
    async def _handle_detected_file(self, job_id: str, file_path: str):
        """
        Handle a detected file from watchdog or life event.
        
        Implements batching to avoid processing files one at a time.
        """
        async with self._processing_lock:
            # Add to pending queue
            if job_id not in self._pending_files:
                self._pending_files[job_id] = []
            
            self._pending_files[job_id].append(file_path)
        
        # Schedule processing after a delay (batching)
        await asyncio.sleep(5)  # Wait 5 seconds for more files
        
        async with self._processing_lock:
            files_to_process = self._pending_files.pop(job_id, [])
        
        if files_to_process:
            await self._process_detected_files(job_id, files_to_process)
    
    async def _process_detected_files(
        self,
        job_id: str,
        file_paths: List[str]
    ):
        """Process detected files for a job"""
        logger.info(f"Processing {len(file_paths)} files for job {job_id}")
        
        async with get_db_context() as db:
            # Get job configuration
            result = await db.execute(
                select(JobDB).where(JobDB.id == job_id)
            )
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"Job not found: {job_id}")
                return
            
            # Determine storage type
            storage_type = StorageType(job.storage_type)
            
            # Create FileInfo objects
            file_infos = []
            for path in file_paths:
                from pathlib import Path
                p = Path(path)
                file_infos.append(FileInfo(
                    name=p.name,
                    path=path,
                    size=p.stat().st_size if p.exists() else 0,
                    is_dir=False,
                    extension=p.suffix,
                    storage_type=storage_type
                ))
            
            # Recognize files
            # TODO: Determine media type from context or job config
            media_type = MediaType.TV  # Default to TV
            
            results = await self.recognition_service.recognize_files(
                file_infos,
                media_type,
                db
            )
            
            # Filter by confidence threshold
            threshold = ConfidenceLevel(job.confidence_threshold)
            threshold_order = {"high": 3, "medium": 2, "low": 1}
            threshold_val = threshold_order.get(threshold.value, 1)
            
            approved_results = [
                r for r in results
                if threshold_order.get(r.confidence.value, 0) >= threshold_val
            ]
            
            logger.info(f"Job {job_id}: {len(approved_results)}/{len(results)} results meet threshold")
            
            # Auto-approve if configured
            if job.auto_approve and approved_results:
                logger.info(f"Auto-approving {len(approved_results)} files for job {job_id}")
                
                # Create dry-run report first
                report = await self.transfer_service.create_dry_run_report(
                    approved_results,
                    storage_type,
                    db
                )
                
                # Execute transfer
                transfer_result = await self.transfer_service.execute_transfer(
                    report.items,
                    storage_type,
                    db
                )
                
                logger.info(
                    f"Job {job_id}: Transferred {transfer_result['transferred_count']}, "
                    f"Failed {transfer_result['failed_count']}"
                )
            else:
                # Queue for manual review
                await event_bus.emit(
                    EventType.JOB_COMPLETED,
                    {
                        "job_id": job_id,
                        "pending_review": len(results) - len(approved_results),
                        "results": [r.model_dump() for r in results]
                    }
                )
            
            # Update job last run time
            job.last_run_at = datetime.utcnow()
            await db.commit()

