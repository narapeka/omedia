"""
115 Life Event Monitor
Monitors 115 cloud storage life events for file changes.
"""

import asyncio
import logging
from typing import Dict, Optional, Callable, Any, List, Set
from datetime import datetime

from ...core.events import event_bus, EventType
from ...core.config import settings
from ...models.schemas import FileInfo, StorageType

logger = logging.getLogger(__name__)


class LifeEventMonitor:
    """Monitors 115 cloud storage life events"""
    
    def __init__(self, on_file_detected: Optional[Callable] = None):
        self._running = False
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._on_file_detected = on_file_detected
        self._client = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._last_event_time: Dict[str, datetime] = {}
    
    async def _ensure_client(self):
        """Ensure 115 client is initialized"""
        if self._client is not None:
            return
        
        cookies = settings.p115.cookies
        if not cookies:
            raise ValueError("115 cookies not configured")
        
        try:
            from p115client import P115Client
            self._client = P115Client(cookies)
            logger.info("115 client initialized for life event monitoring")
        except ImportError:
            raise ImportError("p115client package not installed")
    
    async def start_monitoring(
        self,
        job_id: str,
        path: str,
        event_types: Optional[List[str]] = None
    ) -> bool:
        """
        Start monitoring a path for life events.
        
        Args:
            job_id: Unique job identifier
            path: 115 cloud path to monitor
            event_types: Types of events to monitor
            
        Returns:
            True if started successfully
        """
        if job_id in self._jobs:
            logger.warning(f"Job {job_id} is already being monitored")
            return False
        
        try:
            await self._ensure_client()
            
            self._jobs[job_id] = {
                "path": path,
                "event_types": event_types or ["upload", "move"],
                "enabled": True
            }
            
            # Start the monitor loop if not running
            if not self._running:
                self._running = True
                self._monitor_task = asyncio.create_task(self._monitor_loop())
            
            logger.info(f"Started life event monitoring for job {job_id} on path {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start life event monitoring for job {job_id}: {e}")
            return False
    
    async def stop_monitoring(self, job_id: str) -> bool:
        """
        Stop monitoring a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if stopped successfully
        """
        if job_id not in self._jobs:
            logger.warning(f"Job {job_id} is not being monitored")
            return False
        
        del self._jobs[job_id]
        
        # Stop the monitor loop if no more jobs
        if not self._jobs and self._monitor_task:
            self._running = False
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        
        logger.info(f"Stopped life event monitoring for job {job_id}")
        return True
    
    async def stop_all(self):
        """Stop all monitors"""
        self._running = False
        self._jobs.clear()
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Life event monitor loop started")
        
        while self._running:
            try:
                # Poll for events
                await self._poll_events()
                
                # Wait before next poll
                await asyncio.sleep(30)  # Poll every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in life event monitor loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
        
        logger.info("Life event monitor loop stopped")
    
    async def _poll_events(self):
        """Poll for new life events"""
        if not self._client:
            return
        
        try:
            # Use p115client to get life events
            # This is a simplified implementation - actual implementation
            # would use the life event API from p115strmhelper
            
            # Get recent file changes
            events = await asyncio.to_thread(
                self._client.life_list,
                {"limit": 100}
            )
            
            if not events or events.get("errNo", 0) != 0:
                return
            
            for event in events.get("data", {}).get("list", []):
                await self._process_event(event)
                
        except Exception as e:
            logger.error(f"Error polling life events: {e}")
    
    async def _process_event(self, event: Dict[str, Any]):
        """Process a single life event"""
        try:
            event_type = event.get("type", "")
            file_name = event.get("file_name", "")
            file_path = event.get("file_path", "")
            file_id = event.get("file_id", "")
            event_time = event.get("time", "")
            
            # Check if any job is interested in this path
            for job_id, job_config in self._jobs.items():
                monitored_path = job_config["path"]
                allowed_types = job_config["event_types"]
                
                # Check if event type is monitored
                if event_type not in allowed_types:
                    continue
                
                # Check if file is in monitored path
                if not file_path.startswith(monitored_path):
                    continue
                
                # Check if we've already processed this event
                event_key = f"{job_id}:{file_id}:{event_time}"
                if event_key in self._last_event_time:
                    continue
                
                self._last_event_time[event_key] = datetime.now()
                
                # Create file info
                file_info = FileInfo(
                    name=file_name,
                    path=file_path,
                    file_id=file_id,
                    is_dir=False,
                    storage_type=StorageType.P115
                )
                
                # Emit event
                await event_bus.emit(
                    EventType.LIFE_EVENT_RECEIVED,
                    {
                        "job_id": job_id,
                        "event_type": event_type,
                        "file_info": file_info.model_dump()
                    }
                )
                
                # Call callback
                if self._on_file_detected:
                    await self._on_file_detected(job_id, file_path)
                
                logger.debug(f"Processed life event for {file_name} (job: {job_id})")
                
        except Exception as e:
            logger.error(f"Error processing life event: {e}")
    
    def is_monitoring(self, job_id: str) -> bool:
        """Check if a job is being monitored"""
        return job_id in self._jobs
    
    @property
    def active_jobs(self) -> Set[str]:
        """Get set of active job IDs"""
        return set(self._jobs.keys())

