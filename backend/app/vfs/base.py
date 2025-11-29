"""
Base VFS adapter interface
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, List, Optional, Union
from pathlib import PurePath

from ..models.schemas import StorageType, FileInfo


class VFSError(Exception):
    """Base VFS exception"""
    pass


class VFSNotFoundError(VFSError):
    """File or directory not found"""
    pass


class VFSPermissionError(VFSError):
    """Permission denied"""
    pass


class VFSAdapter(ABC):
    """
    Abstract base class for VFS adapters.
    All storage backends must implement this interface.
    """
    
    storage_type: StorageType
    
    @abstractmethod
    async def list_dir(self, path: str) -> List[FileInfo]:
        """
        List directory contents.
        
        Args:
            path: Directory path
            
        Returns:
            List of FileInfo objects
            
        Raises:
            VFSNotFoundError: If path doesn't exist
            VFSPermissionError: If access denied
        """
        pass
    
    @abstractmethod
    async def get_file_info(self, path: str) -> FileInfo:
        """
        Get information about a file or directory.
        
        Args:
            path: File/directory path
            
        Returns:
            FileInfo object
            
        Raises:
            VFSNotFoundError: If path doesn't exist
        """
        pass
    
    @abstractmethod
    async def exists(self, path: str) -> bool:
        """
        Check if path exists.
        
        Args:
            path: File/directory path
            
        Returns:
            True if exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def is_dir(self, path: str) -> bool:
        """
        Check if path is a directory.
        
        Args:
            path: Path to check
            
        Returns:
            True if directory, False otherwise
        """
        pass
    
    @abstractmethod
    async def mkdir(self, path: str, parents: bool = True) -> bool:
        """
        Create directory.
        
        Args:
            path: Directory path
            parents: Create parent directories if needed
            
        Returns:
            True if created successfully
        """
        pass
    
    @abstractmethod
    async def move(self, src: str, dst: str, overwrite: bool = True) -> bool:
        """
        Move file or directory.
        
        Args:
            src: Source path
            dst: Destination path
            overwrite: Overwrite if destination exists
            
        Returns:
            True if moved successfully
        """
        pass
    
    @abstractmethod
    async def copy(self, src: str, dst: str, overwrite: bool = True) -> bool:
        """
        Copy file or directory.
        
        Args:
            src: Source path
            dst: Destination path
            overwrite: Overwrite if destination exists
            
        Returns:
            True if copied successfully
        """
        pass
    
    @abstractmethod
    async def delete(self, path: str, recursive: bool = False) -> bool:
        """
        Delete file or directory.
        
        Args:
            path: Path to delete
            recursive: Delete directory contents recursively
            
        Returns:
            True if deleted successfully
        """
        pass
    
    @abstractmethod
    async def iter_dir(
        self,
        path: str,
        recursive: bool = False,
        files_only: bool = False
    ) -> AsyncIterator[FileInfo]:
        """
        Iterate directory contents.
        
        Args:
            path: Directory path
            recursive: Include subdirectories recursively
            files_only: Only yield files, not directories
            
        Yields:
            FileInfo objects
        """
        pass
    
    async def walk(
        self,
        path: str,
        files_only: bool = True
    ) -> AsyncIterator[FileInfo]:
        """
        Walk directory tree recursively.
        Convenience method wrapping iter_dir.
        
        Args:
            path: Root directory path
            files_only: Only yield files
            
        Yields:
            FileInfo objects
        """
        async for item in self.iter_dir(path, recursive=True, files_only=files_only):
            yield item
    
    def normalize_path(self, path: str) -> str:
        """
        Normalize path for this storage backend.
        
        Args:
            path: Path to normalize
            
        Returns:
            Normalized path string
        """
        # Default implementation - subclasses can override
        return str(PurePath(path))
    
    def join_path(self, *parts: str) -> str:
        """
        Join path parts.
        
        Args:
            *parts: Path parts to join
            
        Returns:
            Joined path string
        """
        return str(PurePath(*parts))
    
    def get_parent(self, path: str) -> str:
        """
        Get parent directory path.
        
        Args:
            path: File/directory path
            
        Returns:
            Parent directory path
        """
        return str(PurePath(path).parent)
    
    def get_name(self, path: str) -> str:
        """
        Get file/directory name from path.
        
        Args:
            path: File/directory path
            
        Returns:
            Name (last component of path)
        """
        return PurePath(path).name
    
    def get_extension(self, path: str) -> str:
        """
        Get file extension.
        
        Args:
            path: File path
            
        Returns:
            Extension including dot (e.g., ".mp4") or empty string
        """
        return PurePath(path).suffix
    
    def get_stem(self, path: str) -> str:
        """
        Get filename without extension.
        
        Args:
            path: File path
            
        Returns:
            Filename without extension
        """
        return PurePath(path).stem

