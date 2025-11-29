"""
VFS adapter factory
"""

from typing import Dict, Optional, Type

from .base import VFSAdapter, VFSError
from .local_adapter import LocalAdapter
from .p115_adapter import P115Adapter
from .webdav_adapter import WebDAVAdapter
from ..models.schemas import StorageType


# Registry of VFS adapters
_adapters: Dict[StorageType, Type[VFSAdapter]] = {
    StorageType.LOCAL: LocalAdapter,
    StorageType.P115: P115Adapter,
    StorageType.WEBDAV: WebDAVAdapter,
}

# Cached adapter instances
_instances: Dict[str, VFSAdapter] = {}


def register_adapter(storage_type: StorageType, adapter_class: Type[VFSAdapter]) -> None:
    """
    Register a VFS adapter class.
    
    Args:
        storage_type: Storage type for this adapter
        adapter_class: VFSAdapter subclass
    """
    _adapters[storage_type] = adapter_class


def get_vfs_adapter(
    storage_type: StorageType,
    **kwargs
) -> VFSAdapter:
    """
    Get a VFS adapter instance.
    
    Args:
        storage_type: Type of storage
        **kwargs: Additional arguments for adapter initialization
        
    Returns:
        VFSAdapter instance
        
    Raises:
        VFSError: If adapter not available
    """
    if storage_type not in _adapters:
        raise VFSError(f"No adapter registered for storage type: {storage_type}")
    
    # Create cache key
    cache_key = f"{storage_type.value}:{hash(frozenset(kwargs.items()))}"
    
    # Return cached instance if available
    if cache_key in _instances:
        return _instances[cache_key]
    
    # Create new instance
    adapter_class = _adapters[storage_type]
    instance = adapter_class(**kwargs)
    
    # Cache the instance
    _instances[cache_key] = instance
    
    return instance


def clear_adapter_cache() -> None:
    """Clear all cached adapter instances"""
    _instances.clear()

