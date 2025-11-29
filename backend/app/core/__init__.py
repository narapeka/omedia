"""
Core module - Configuration, Database, and Events
"""

from .config import settings
from .database import get_db, init_db
from .events import event_bus

__all__ = ["settings", "get_db", "init_db", "event_bus"]

