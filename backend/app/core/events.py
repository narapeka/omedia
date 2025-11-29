"""
Simple event bus for extensibility hooks
Provides a lightweight pub/sub mechanism for decoupled components.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime


logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Event types for the event bus"""
    # Recognition events
    RECOGNITION_STARTED = "recognition.started"
    RECOGNITION_COMPLETED = "recognition.completed"
    RECOGNITION_FAILED = "recognition.failed"
    
    # Transfer events
    TRANSFER_STARTED = "transfer.started"
    TRANSFER_PROGRESS = "transfer.progress"
    TRANSFER_COMPLETED = "transfer.completed"
    TRANSFER_FAILED = "transfer.failed"
    
    # Share link events
    SHARE_LINK_RECEIVED = "share.link_received"
    SHARE_FILES_LISTED = "share.files_listed"
    SHARE_SAVE_STARTED = "share.save_started"
    SHARE_SAVE_COMPLETED = "share.save_completed"
    
    # Job events
    JOB_STARTED = "job.started"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    
    # Watchdog events
    WATCHDOG_FILE_CREATED = "watchdog.file_created"
    WATCHDOG_FILE_MODIFIED = "watchdog.file_modified"
    WATCHDOG_FILE_DELETED = "watchdog.file_deleted"
    
    # 115 Life events
    LIFE_EVENT_RECEIVED = "life.event_received"
    LIFE_FILE_UPLOADED = "life.file_uploaded"
    LIFE_FILE_MOVED = "life.file_moved"
    
    # Extension hooks
    PRE_TRANSFER = "hook.pre_transfer"
    POST_TRANSFER = "hook.post_transfer"
    PRE_RECOGNITION = "hook.pre_recognition"
    POST_RECOGNITION = "hook.post_recognition"


@dataclass
class Event:
    """Event data container"""
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    
    def __str__(self) -> str:
        return f"Event({self.type.value}, source={self.source})"


# Type alias for event handlers
EventHandler = Callable[[Event], Union[None, asyncio.coroutine]]


class EventBus:
    """
    Simple event bus implementation.
    Supports both sync and async handlers.
    """
    
    def __init__(self):
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._global_handlers: List[EventHandler] = []
        self._lock = asyncio.Lock()
    
    def subscribe(
        self,
        event_type: EventType,
        handler: EventHandler
    ) -> Callable[[], None]:
        """
        Subscribe to an event type.
        
        Args:
            event_type: The event type to subscribe to
            handler: The handler function (sync or async)
            
        Returns:
            Unsubscribe function
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler subscribed to {event_type.value}")
        
        def unsubscribe():
            if event_type in self._handlers and handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)
                logger.debug(f"Handler unsubscribed from {event_type.value}")
        
        return unsubscribe
    
    def subscribe_all(self, handler: EventHandler) -> Callable[[], None]:
        """
        Subscribe to all events.
        
        Args:
            handler: The handler function (sync or async)
            
        Returns:
            Unsubscribe function
        """
        self._global_handlers.append(handler)
        logger.debug("Global handler subscribed")
        
        def unsubscribe():
            if handler in self._global_handlers:
                self._global_handlers.remove(handler)
                logger.debug("Global handler unsubscribed")
        
        return unsubscribe
    
    def on(self, event_type: EventType):
        """
        Decorator for subscribing to events.
        
        Usage:
            @event_bus.on(EventType.TRANSFER_COMPLETED)
            async def handle_transfer(event: Event):
                ...
        """
        def decorator(handler: EventHandler) -> EventHandler:
            self.subscribe(event_type, handler)
            return handler
        return decorator
    
    async def emit(
        self,
        event_type: EventType,
        data: Optional[Dict[str, Any]] = None,
        source: str = ""
    ) -> None:
        """
        Emit an event to all subscribers.
        
        Args:
            event_type: The event type
            data: Event data dictionary
            source: Event source identifier
        """
        event = Event(
            type=event_type,
            data=data or {},
            source=source
        )
        
        logger.debug(f"Emitting event: {event}")
        
        handlers = self._handlers.get(event_type, []) + self._global_handlers
        
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in event handler for {event_type.value}: {e}")
    
    def emit_sync(
        self,
        event_type: EventType,
        data: Optional[Dict[str, Any]] = None,
        source: str = ""
    ) -> None:
        """
        Emit an event synchronously (fire and forget for async handlers).
        Useful when called from sync code.
        """
        event = Event(
            type=event_type,
            data=data or {},
            source=source
        )
        
        logger.debug(f"Emitting event (sync): {event}")
        
        handlers = self._handlers.get(event_type, []) + self._global_handlers
        
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    # Schedule the coroutine to run
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        # No running loop, run in new loop
                        asyncio.run(result)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type.value}: {e}")
    
    def clear(self, event_type: Optional[EventType] = None) -> None:
        """
        Clear event handlers.
        
        Args:
            event_type: If provided, clear only handlers for this type.
                       If None, clear all handlers.
        """
        if event_type is None:
            self._handlers.clear()
            self._global_handlers.clear()
            logger.debug("All event handlers cleared")
        elif event_type in self._handlers:
            self._handlers[event_type].clear()
            logger.debug(f"Handlers cleared for {event_type.value}")


# Global event bus instance
event_bus = EventBus()

