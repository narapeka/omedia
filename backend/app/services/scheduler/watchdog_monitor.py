"""
Watchdog Monitor
Monitors local filesystem for new files using polling.
"""

import asyncio
import logging
from typing import Dict, Set, Optional, Callable, Any
from pathlib import Path
from datetime import datetime

from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent

from ...core.events import event_bus, EventType
from ...models.schemas import FileInfo, StorageType

logger = logging.getLogger(__name__)


# Video extensions to monitor
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", 
    ".webm", ".m4v", ".ts", ".m2ts"
}


class MediaFileHandler(FileSystemEventHandler):
    """Handler for filesystem events"""
    
    def __init__(
        self,
        job_id: str,
        callback: Callable[[str, str], Any],
        loop: asyncio.AbstractEventLoop
    ):
        self.job_id = job_id
        self.callback = callback
        self.loop = loop
    
    def _is_video_file(self, path: str) -> bool:
        """Check if path is a video file"""
        return Path(path).suffix.lower() in VIDEO_EXTENSIONS
    
    def on_created(self, event):
        """Handle file creation"""
        if event.is_directory:
            return
        
        if self._is_video_file(event.src_path):
            logger.debug(f"New video file: {event.src_path}")
            asyncio.run_coroutine_threadsafe(
                self._emit_event("created", event.src_path),
                self.loop
            )
    
    def on_moved(self, event):
        """Handle file move"""
        if event.is_directory:
            return
        
        if self._is_video_file(event.dest_path):
            logger.debug(f"Video file moved: {event.dest_path}")
            asyncio.run_coroutine_threadsafe(
                self._emit_event("moved", event.dest_path),
                self.loop
            )
    
    async def _emit_event(self, event_type: str, path: str):
        """Emit event and call callback"""
        file_info = FileInfo(
            name=Path(path).name,
            path=path,
            size=Path(path).stat().st_size if Path(path).exists() else 0,
            is_dir=False,
            extension=Path(path).suffix,
            modified_time=datetime.now(),
            storage_type=StorageType.LOCAL
        )
        
        await event_bus.emit(
            EventType.WATCHDOG_FILE_CREATED if event_type == "created" else EventType.WATCHDOG_FILE_MODIFIED,
            {
                "job_id": self.job_id,
                "file_info": file_info.model_dump(),
                "path": path
            }
        )
        
        # Call the callback
        if self.callback:
            await self.callback(self.job_id, path)


class WatchdogMonitor:
    """Monitors local paths for new media files"""
    
    def __init__(self, on_file_detected: Optional[Callable] = None):
        self._observers: Dict[str, PollingObserver] = {}
        self._running = False
        self._on_file_detected = on_file_detected
    
    def start_monitoring(
        self,
        job_id: str,
        path: str,
        poll_interval: int = 60
    ) -> bool:
        """
        Start monitoring a path.
        
        Args:
            job_id: Unique job identifier
            path: Path to monitor
            poll_interval: Polling interval in seconds
            
        Returns:
            True if started successfully
        """
        if job_id in self._observers:
            logger.warning(f"Job {job_id} is already being monitored")
            return False
        
        if not Path(path).exists():
            logger.error(f"Path does not exist: {path}")
            return False
        
        try:
            # Get event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            
            # Create handler
            handler = MediaFileHandler(
                job_id=job_id,
                callback=self._on_file_detected,
                loop=loop
            )
            
            # Create polling observer
            observer = PollingObserver(timeout=poll_interval)
            observer.schedule(handler, path, recursive=True)
            observer.start()
            
            self._observers[job_id] = observer
            self._running = True
            
            logger.info(f"Started monitoring {path} for job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start monitoring for job {job_id}: {e}")
            return False
    
    def stop_monitoring(self, job_id: str) -> bool:
        """
        Stop monitoring a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if stopped successfully
        """
        if job_id not in self._observers:
            logger.warning(f"Job {job_id} is not being monitored")
            return False
        
        try:
            observer = self._observers[job_id]
            observer.stop()
            observer.join(timeout=5)
            
            del self._observers[job_id]
            
            logger.info(f"Stopped monitoring for job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop monitoring for job {job_id}: {e}")
            return False
    
    def stop_all(self):
        """Stop all monitors"""
        for job_id in list(self._observers.keys()):
            self.stop_monitoring(job_id)
        
        self._running = False
    
    def is_monitoring(self, job_id: str) -> bool:
        """Check if a job is being monitored"""
        return job_id in self._observers
    
    @property
    def active_jobs(self) -> Set[str]:
        """Get set of active job IDs"""
        return set(self._observers.keys())

