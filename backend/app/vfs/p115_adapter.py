"""
115 Cloud Storage VFS adapter
Uses p115client for API interactions.
"""

import asyncio
import logging
from datetime import datetime
from typing import AsyncIterator, List, Optional, Dict, Any
from pathlib import PurePosixPath

from .base import VFSAdapter, VFSError, VFSNotFoundError, VFSPermissionError
from ..models.schemas import StorageType, FileInfo
from ..core.config import settings

logger = logging.getLogger(__name__)


class P115Adapter(VFSAdapter):
    """VFS adapter for 115 cloud storage"""
    
    storage_type = StorageType.P115
    
    def __init__(self, cookies: Optional[str] = None):
        """
        Initialize 115 adapter.
        
        Args:
            cookies: 115 cookies string. If None, uses settings.
        """
        self._cookies = cookies or settings.p115.cookies
        self._client = None
        self._fs = None
        self._initialized = False
    
    async def _ensure_initialized(self):
        """Ensure client is initialized"""
        if self._initialized:
            return
        
        if not self._cookies:
            raise VFSError("115 cookies not configured")
        
        try:
            # Import p115client
            from p115client import P115Client
            
            # Initialize client with cookies
            self._client = P115Client(self._cookies)
            self._initialized = True
            logger.info("P115 client initialized successfully")
        except ImportError:
            raise VFSError("p115client package not installed")
        except Exception as e:
            raise VFSError(f"Failed to initialize 115 client: {e}")
    
    def _parse_file_item(self, item: Dict[str, Any], parent_path: str = "") -> FileInfo:
        """Parse 115 API file item to FileInfo"""
        name = item.get("name", item.get("n", ""))
        is_dir = item.get("fc", item.get("fid")) is None  # No file_id means directory
        
        # Build full path
        if parent_path:
            path = str(PurePosixPath(parent_path) / name)
        else:
            path = "/" + name
        
        # Get file size
        size = int(item.get("size", item.get("s", 0)))
        
        # Get modification time
        mtime = item.get("te", item.get("t", ""))
        modified_time = None
        if mtime:
            try:
                if isinstance(mtime, (int, float)):
                    modified_time = datetime.fromtimestamp(mtime)
                else:
                    modified_time = datetime.strptime(mtime, "%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                pass
        
        # Get extension
        extension = None
        if not is_dir and "." in name:
            extension = "." + name.rsplit(".", 1)[-1].lower()
        
        return FileInfo(
            name=name,
            path=path,
            size=size,
            is_dir=is_dir,
            extension=extension,
            modified_time=modified_time,
            pickcode=item.get("pc", item.get("pickcode")),
            file_id=str(item.get("fid", item.get("cid", ""))),
            storage_type=StorageType.P115
        )
    
    async def list_dir(self, path: str) -> List[FileInfo]:
        """List directory contents"""
        await self._ensure_initialized()
        
        try:
            # Normalize path
            path = path.strip()
            if not path.startswith("/"):
                path = "/" + path
            
            # Get directory ID
            cid = await self._get_dir_id(path)
            if cid is None:
                raise VFSNotFoundError(f"Path not found: {path}")
            
            # List files in directory
            files = []
            async for item in self._iter_dir_by_cid(cid):
                files.append(self._parse_file_item(item, path))
            
            return files
            
        except VFSNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            raise VFSError(f"Failed to list directory: {path}") from e
    
    async def _get_dir_id(self, path: str) -> Optional[str]:
        """Get directory ID (cid) from path"""
        if path == "/" or path == "":
            return "0"  # Root directory
        
        # Navigate path components
        parts = [p for p in path.split("/") if p]
        current_cid = "0"
        
        for part in parts:
            found = False
            async for item in self._iter_dir_by_cid(current_cid):
                name = item.get("name", item.get("n", ""))
                if name == part:
                    # Check if it's a directory
                    cid = item.get("cid")
                    if cid:
                        current_cid = str(cid)
                        found = True
                        break
            
            if not found:
                return None
        
        return current_cid
    
    async def _iter_dir_by_cid(self, cid: str) -> AsyncIterator[Dict[str, Any]]:
        """Iterate directory contents by cid"""
        try:
            # Use p115client to list files
            offset = 0
            limit = 1000
            
            while True:
                # Call 115 API to list files
                resp = await asyncio.to_thread(
                    self._client.fs_files,
                    {"cid": cid, "offset": offset, "limit": limit}
                )
                
                if not resp or resp.get("errNo", 0) != 0:
                    break
                
                data = resp.get("data", [])
                if not data:
                    break
                
                for item in data:
                    yield item
                
                # Check if there are more pages
                if len(data) < limit:
                    break
                    
                offset += limit
                
        except Exception as e:
            logger.error(f"Error iterating directory {cid}: {e}")
            raise
    
    async def get_file_info(self, path: str) -> FileInfo:
        """Get file/directory information"""
        await self._ensure_initialized()
        
        if path == "/" or path == "":
            return FileInfo(
                name="",
                path="/",
                size=0,
                is_dir=True,
                storage_type=StorageType.P115
            )
        
        # Get parent directory and filename
        path_obj = PurePosixPath(path)
        parent_path = str(path_obj.parent)
        name = path_obj.name
        
        # List parent directory and find the file
        items = await self.list_dir(parent_path)
        for item in items:
            if item.name == name:
                return item
        
        raise VFSNotFoundError(f"Path not found: {path}")
    
    async def exists(self, path: str) -> bool:
        """Check if path exists"""
        try:
            await self.get_file_info(path)
            return True
        except VFSNotFoundError:
            return False
    
    async def is_dir(self, path: str) -> bool:
        """Check if path is a directory"""
        try:
            info = await self.get_file_info(path)
            return info.is_dir
        except VFSNotFoundError:
            return False
    
    async def mkdir(self, path: str, parents: bool = True) -> bool:
        """Create directory"""
        await self._ensure_initialized()
        
        try:
            path = path.strip()
            if not path.startswith("/"):
                path = "/" + path
            
            if await self.exists(path):
                return True  # Already exists
            
            # Get parent directory ID
            parent_path = str(PurePosixPath(path).parent)
            name = PurePosixPath(path).name
            
            if parents and parent_path != "/" and not await self.exists(parent_path):
                # Create parent directories
                await self.mkdir(parent_path, parents=True)
            
            parent_cid = await self._get_dir_id(parent_path)
            if parent_cid is None:
                raise VFSNotFoundError(f"Parent directory not found: {parent_path}")
            
            # Create directory using 115 API
            resp = await asyncio.to_thread(
                self._client.fs_mkdir,
                {"pid": parent_cid, "cname": name}
            )
            
            if resp and resp.get("state", False):
                return True
            
            raise VFSError(f"Failed to create directory: {path}")
            
        except VFSNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}")
            raise VFSError(f"Failed to create directory: {path}") from e
    
    async def move(self, src: str, dst: str, overwrite: bool = True) -> bool:
        """Move file or directory"""
        await self._ensure_initialized()
        
        try:
            # Get source file info
            src_info = await self.get_file_info(src)
            
            # Get destination parent directory
            dst_path = PurePosixPath(dst)
            dst_parent = str(dst_path.parent)
            dst_name = dst_path.name
            
            # Ensure destination directory exists
            if not await self.exists(dst_parent):
                await self.mkdir(dst_parent, parents=True)
            
            dst_cid = await self._get_dir_id(dst_parent)
            if dst_cid is None:
                raise VFSNotFoundError(f"Destination directory not found: {dst_parent}")
            
            # Check if we need to rename
            rename_needed = src_info.name != dst_name
            
            # Move file using 115 API
            fid = src_info.file_id
            if src_info.is_dir:
                # Move directory
                resp = await asyncio.to_thread(
                    self._client.fs_move,
                    {"fid[]": fid, "pid": dst_cid}
                )
            else:
                resp = await asyncio.to_thread(
                    self._client.fs_move,
                    {"fid[]": fid, "pid": dst_cid}
                )
            
            if not resp or not resp.get("state", False):
                raise VFSError(f"Failed to move: {src} -> {dst}")
            
            # Rename if needed
            if rename_needed:
                resp = await asyncio.to_thread(
                    self._client.fs_rename,
                    {"fid": fid, "file_name": dst_name}
                )
                
                if not resp or not resp.get("state", False):
                    logger.warning(f"Failed to rename file after move: {src_info.name} -> {dst_name}")
            
            return True
            
        except VFSNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error moving {src} -> {dst}: {e}")
            raise VFSError(f"Failed to move: {src} -> {dst}") from e
    
    async def copy(self, src: str, dst: str, overwrite: bool = True) -> bool:
        """Copy file or directory"""
        await self._ensure_initialized()
        
        try:
            # Get source file info
            src_info = await self.get_file_info(src)
            
            # Get destination parent directory
            dst_path = PurePosixPath(dst)
            dst_parent = str(dst_path.parent)
            
            # Ensure destination directory exists
            if not await self.exists(dst_parent):
                await self.mkdir(dst_parent, parents=True)
            
            dst_cid = await self._get_dir_id(dst_parent)
            if dst_cid is None:
                raise VFSNotFoundError(f"Destination directory not found: {dst_parent}")
            
            # Copy file using 115 API
            fid = src_info.file_id
            resp = await asyncio.to_thread(
                self._client.fs_copy,
                {"fid[]": fid, "pid": dst_cid}
            )
            
            if resp and resp.get("state", False):
                return True
            
            raise VFSError(f"Failed to copy: {src} -> {dst}")
            
        except VFSNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error copying {src} -> {dst}: {e}")
            raise VFSError(f"Failed to copy: {src} -> {dst}") from e
    
    async def delete(self, path: str, recursive: bool = False) -> bool:
        """Delete file or directory"""
        await self._ensure_initialized()
        
        try:
            file_info = await self.get_file_info(path)
            
            # Delete using 115 API
            fid = file_info.file_id
            resp = await asyncio.to_thread(
                self._client.fs_delete,
                {"fid[]": fid}
            )
            
            if resp and resp.get("state", False):
                return True
            
            raise VFSError(f"Failed to delete: {path}")
            
        except VFSNotFoundError:
            return True  # Already doesn't exist
        except Exception as e:
            logger.error(f"Error deleting {path}: {e}")
            raise VFSError(f"Failed to delete: {path}") from e
    
    async def iter_dir(
        self,
        path: str,
        recursive: bool = False,
        files_only: bool = False
    ) -> AsyncIterator[FileInfo]:
        """Iterate directory contents"""
        await self._ensure_initialized()
        
        items = await self.list_dir(path)
        
        for item in items:
            if files_only and item.is_dir:
                if recursive:
                    async for sub_item in self.iter_dir(item.path, recursive=True, files_only=True):
                        yield sub_item
            else:
                yield item
                if recursive and item.is_dir:
                    async for sub_item in self.iter_dir(item.path, recursive=True, files_only=files_only):
                        yield sub_item
    
    # ============ 115-specific methods ============
    
    async def receive_share(
        self,
        share_code: str,
        receive_code: Optional[str] = None,
        target_path: str = "/",
        file_ids: Optional[List[str]] = None
    ) -> bool:
        """
        Receive files from a share link.
        
        Args:
            share_code: Share code from URL
            receive_code: Optional receive code (password)
            target_path: Target directory path
            file_ids: Optional list of specific file IDs to receive
            
        Returns:
            True if successful
        """
        await self._ensure_initialized()
        
        try:
            # Get target directory ID
            target_cid = await self._get_dir_id(target_path)
            if target_cid is None:
                # Create target directory
                await self.mkdir(target_path, parents=True)
                target_cid = await self._get_dir_id(target_path)
            
            # Receive share using 115 API
            params = {
                "share_code": share_code,
                "cid": target_cid
            }
            if receive_code:
                params["receive_code"] = receive_code
            if file_ids:
                params["file_id"] = ",".join(file_ids)
            
            resp = await asyncio.to_thread(
                self._client.share_receive,
                params
            )
            
            if resp and resp.get("state", False):
                return True
            
            error = resp.get("error", "Unknown error")
            raise VFSError(f"Failed to receive share: {error}")
            
        except Exception as e:
            logger.error(f"Error receiving share {share_code}: {e}")
            raise VFSError(f"Failed to receive share: {share_code}") from e
    
    async def list_share(
        self,
        share_code: str,
        receive_code: Optional[str] = None,
        path: str = "/"
    ) -> List[FileInfo]:
        """
        List files in a share link.
        
        Args:
            share_code: Share code from URL
            receive_code: Optional receive code (password)
            path: Path within the share
            
        Returns:
            List of FileInfo objects
        """
        await self._ensure_initialized()
        
        try:
            params = {"share_code": share_code}
            if receive_code:
                params["receive_code"] = receive_code
            
            # Get share snap to list files
            resp = await asyncio.to_thread(
                self._client.share_snap,
                params
            )
            
            if not resp or resp.get("errNo", 0) != 0:
                error = resp.get("error", "Unknown error") if resp else "No response"
                raise VFSError(f"Failed to list share: {error}")
            
            files = []
            data = resp.get("data", {})
            
            # Parse file list
            for item in data.get("list", []):
                files.append(self._parse_file_item(item, path))
            
            return files
            
        except Exception as e:
            logger.error(f"Error listing share {share_code}: {e}")
            raise VFSError(f"Failed to list share: {share_code}") from e

