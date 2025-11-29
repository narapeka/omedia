"""
Virtual File System (VFS) Abstraction Layer
Provides unified interface for different storage backends.
"""

from .base import VFSAdapter, VFSError, VFSNotFoundError, VFSPermissionError
from .local_adapter import LocalAdapter
from .p115_adapter import P115Adapter
from .webdav_adapter import WebDAVAdapter
from .factory import get_vfs_adapter, register_adapter

__all__ = [
    "VFSAdapter",
    "VFSError",
    "VFSNotFoundError",
    "VFSPermissionError",
    "LocalAdapter",
    "P115Adapter",
    "WebDAVAdapter",
    "get_vfs_adapter",
    "register_adapter",
]

