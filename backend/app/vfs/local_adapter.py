"""
Local filesystem VFS adapter
"""

import os
import shutil
import asyncio
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, List

from .base import VFSAdapter, VFSError, VFSNotFoundError, VFSPermissionError
from ..models.schemas import StorageType, FileInfo


class LocalAdapter(VFSAdapter):
    """VFS adapter for local filesystem"""
    
    storage_type = StorageType.LOCAL
    
    def __init__(self, base_path: str = ""):
        """
        Initialize local adapter.
        
        Args:
            base_path: Optional base path to prepend to all paths
        """
        self.base_path = Path(base_path) if base_path else None
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to base_path"""
        p = Path(path)
        if self.base_path and not p.is_absolute():
            p = self.base_path / p
        return p.resolve()
    
    def _file_info_from_path(self, path: Path) -> FileInfo:
        """Create FileInfo from Path object"""
        stat = path.stat()
        return FileInfo(
            name=path.name,
            path=str(path),
            size=stat.st_size if path.is_file() else 0,
            is_dir=path.is_dir(),
            extension=path.suffix if path.is_file() else None,
            modified_time=datetime.fromtimestamp(stat.st_mtime),
            storage_type=StorageType.LOCAL
        )
    
    async def list_dir(self, path: str) -> List[FileInfo]:
        """List directory contents"""
        resolved = self._resolve_path(path)
        
        if not resolved.exists():
            raise VFSNotFoundError(f"Path not found: {path}")
        
        if not resolved.is_dir():
            raise VFSError(f"Not a directory: {path}")
        
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            items = await loop.run_in_executor(None, list, resolved.iterdir())
            return [self._file_info_from_path(item) for item in items]
        except PermissionError as e:
            raise VFSPermissionError(f"Permission denied: {path}") from e
    
    async def get_file_info(self, path: str) -> FileInfo:
        """Get file/directory information"""
        resolved = self._resolve_path(path)
        
        if not resolved.exists():
            raise VFSNotFoundError(f"Path not found: {path}")
        
        return self._file_info_from_path(resolved)
    
    async def exists(self, path: str) -> bool:
        """Check if path exists"""
        return self._resolve_path(path).exists()
    
    async def is_dir(self, path: str) -> bool:
        """Check if path is a directory"""
        resolved = self._resolve_path(path)
        return resolved.exists() and resolved.is_dir()
    
    async def mkdir(self, path: str, parents: bool = True) -> bool:
        """Create directory"""
        resolved = self._resolve_path(path)
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: resolved.mkdir(parents=parents, exist_ok=True)
            )
            return True
        except Exception as e:
            raise VFSError(f"Failed to create directory: {path}") from e
    
    async def move(self, src: str, dst: str, overwrite: bool = True) -> bool:
        """Move file or directory"""
        src_path = self._resolve_path(src)
        dst_path = self._resolve_path(dst)
        
        if not src_path.exists():
            raise VFSNotFoundError(f"Source not found: {src}")
        
        if dst_path.exists():
            if not overwrite:
                raise VFSError(f"Destination already exists: {dst}")
            # Remove destination
            loop = asyncio.get_event_loop()
            if dst_path.is_dir():
                await loop.run_in_executor(None, shutil.rmtree, dst_path)
            else:
                await loop.run_in_executor(None, dst_path.unlink)
        
        # Ensure parent directory exists
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.move, str(src_path), str(dst_path))
            return True
        except Exception as e:
            raise VFSError(f"Failed to move: {src} -> {dst}") from e
    
    async def copy(self, src: str, dst: str, overwrite: bool = True) -> bool:
        """Copy file or directory"""
        src_path = self._resolve_path(src)
        dst_path = self._resolve_path(dst)
        
        if not src_path.exists():
            raise VFSNotFoundError(f"Source not found: {src}")
        
        if dst_path.exists():
            if not overwrite:
                raise VFSError(f"Destination already exists: {dst}")
            # Remove destination
            loop = asyncio.get_event_loop()
            if dst_path.is_dir():
                await loop.run_in_executor(None, shutil.rmtree, dst_path)
            else:
                await loop.run_in_executor(None, dst_path.unlink)
        
        # Ensure parent directory exists
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            loop = asyncio.get_event_loop()
            if src_path.is_dir():
                await loop.run_in_executor(None, shutil.copytree, str(src_path), str(dst_path))
            else:
                await loop.run_in_executor(None, shutil.copy2, str(src_path), str(dst_path))
            return True
        except Exception as e:
            raise VFSError(f"Failed to copy: {src} -> {dst}") from e
    
    async def delete(self, path: str, recursive: bool = False) -> bool:
        """Delete file or directory"""
        resolved = self._resolve_path(path)
        
        if not resolved.exists():
            return True  # Already doesn't exist
        
        try:
            loop = asyncio.get_event_loop()
            if resolved.is_dir():
                if recursive:
                    await loop.run_in_executor(None, shutil.rmtree, resolved)
                else:
                    await loop.run_in_executor(None, resolved.rmdir)
            else:
                await loop.run_in_executor(None, resolved.unlink)
            return True
        except Exception as e:
            raise VFSError(f"Failed to delete: {path}") from e
    
    async def iter_dir(
        self,
        path: str,
        recursive: bool = False,
        files_only: bool = False
    ) -> AsyncIterator[FileInfo]:
        """Iterate directory contents"""
        resolved = self._resolve_path(path)
        
        if not resolved.exists():
            raise VFSNotFoundError(f"Path not found: {path}")
        
        if not resolved.is_dir():
            raise VFSError(f"Not a directory: {path}")
        
        if recursive:
            # Use os.walk for recursive iteration
            loop = asyncio.get_event_loop()
            
            def _walk():
                for root, dirs, files in os.walk(resolved):
                    root_path = Path(root)
                    if not files_only:
                        for d in dirs:
                            yield root_path / d
                    for f in files:
                        yield root_path / f
            
            for item_path in await loop.run_in_executor(None, lambda: list(_walk())):
                try:
                    yield self._file_info_from_path(item_path)
                except (FileNotFoundError, PermissionError):
                    continue
        else:
            for item in resolved.iterdir():
                if files_only and item.is_dir():
                    continue
                try:
                    yield self._file_info_from_path(item)
                except (FileNotFoundError, PermissionError):
                    continue

