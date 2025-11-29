"""
WebDAV VFS adapter
Provides access to WebDAV servers.
"""

import asyncio
import logging
from datetime import datetime
from typing import AsyncIterator, List, Optional
from pathlib import PurePosixPath
from urllib.parse import urljoin

import httpx

from .base import VFSAdapter, VFSError, VFSNotFoundError, VFSPermissionError
from ..models.schemas import StorageType, FileInfo
from ..core.config import settings

logger = logging.getLogger(__name__)


class WebDAVAdapter(VFSAdapter):
    """VFS adapter for WebDAV servers"""
    
    storage_type = StorageType.WEBDAV
    
    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize WebDAV adapter.
        
        Args:
            url: WebDAV server URL
            username: Authentication username
            password: Authentication password
        """
        self._url = url or settings.storage.webdav_url
        self._username = username or settings.storage.webdav_username
        self._password = password or settings.storage.webdav_password
        
        if not self._url:
            raise VFSError("WebDAV URL not configured")
        
        # Ensure URL ends with /
        if not self._url.endswith("/"):
            self._url += "/"
        
        # Create HTTP client
        auth = None
        if self._username and self._password:
            auth = (self._username, self._password)
        
        self._client = httpx.AsyncClient(
            auth=auth,
            timeout=30.0,
            follow_redirects=True
        )
    
    def _full_url(self, path: str) -> str:
        """Get full URL for a path"""
        path = path.lstrip("/")
        return urljoin(self._url, path)
    
    def _parse_propfind_response(
        self,
        xml_text: str,
        base_path: str
    ) -> List[FileInfo]:
        """Parse PROPFIND XML response"""
        import xml.etree.ElementTree as ET
        
        # XML namespaces
        ns = {
            "d": "DAV:",
        }
        
        items = []
        
        try:
            root = ET.fromstring(xml_text)
            
            for response in root.findall(".//d:response", ns):
                href_elem = response.find("d:href", ns)
                if href_elem is None:
                    continue
                
                href = href_elem.text or ""
                
                # Get properties
                propstat = response.find("d:propstat", ns)
                if propstat is None:
                    continue
                
                prop = propstat.find("d:prop", ns)
                if prop is None:
                    continue
                
                # Check if it's a collection (directory)
                resourcetype = prop.find("d:resourcetype", ns)
                is_dir = resourcetype is not None and resourcetype.find("d:collection", ns) is not None
                
                # Get display name or derive from href
                displayname = prop.find("d:displayname", ns)
                name = displayname.text if displayname is not None and displayname.text else href.rstrip("/").split("/")[-1]
                
                # Skip the base path itself
                if not name or href.rstrip("/") == base_path.rstrip("/"):
                    continue
                
                # Get content length
                contentlength = prop.find("d:getcontentlength", ns)
                size = int(contentlength.text) if contentlength is not None and contentlength.text else 0
                
                # Get last modified
                lastmodified = prop.find("d:getlastmodified", ns)
                modified_time = None
                if lastmodified is not None and lastmodified.text:
                    try:
                        # Parse RFC 2822 date
                        from email.utils import parsedate_to_datetime
                        modified_time = parsedate_to_datetime(lastmodified.text)
                    except (ValueError, TypeError):
                        pass
                
                # Get extension
                extension = None
                if not is_dir and "." in name:
                    extension = "." + name.rsplit(".", 1)[-1].lower()
                
                # Build full path
                path = str(PurePosixPath(base_path) / name)
                
                items.append(FileInfo(
                    name=name,
                    path=path,
                    size=size,
                    is_dir=is_dir,
                    extension=extension,
                    modified_time=modified_time,
                    storage_type=StorageType.WEBDAV
                ))
                
        except ET.ParseError as e:
            logger.error(f"Failed to parse PROPFIND response: {e}")
        
        return items
    
    async def list_dir(self, path: str) -> List[FileInfo]:
        """List directory contents"""
        try:
            url = self._full_url(path)
            
            # PROPFIND request with depth 1
            response = await self._client.request(
                "PROPFIND",
                url,
                headers={"Depth": "1"},
                content='<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:allprop/></d:propfind>'
            )
            
            if response.status_code == 404:
                raise VFSNotFoundError(f"Path not found: {path}")
            
            if response.status_code == 401:
                raise VFSPermissionError("Authentication failed")
            
            response.raise_for_status()
            
            return self._parse_propfind_response(response.text, path)
            
        except VFSNotFoundError:
            raise
        except VFSPermissionError:
            raise
        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            raise VFSError(f"Failed to list directory: {path}") from e
    
    async def get_file_info(self, path: str) -> FileInfo:
        """Get file/directory information"""
        try:
            url = self._full_url(path)
            
            # PROPFIND request with depth 0
            response = await self._client.request(
                "PROPFIND",
                url,
                headers={"Depth": "0"},
                content='<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:allprop/></d:propfind>'
            )
            
            if response.status_code == 404:
                raise VFSNotFoundError(f"Path not found: {path}")
            
            response.raise_for_status()
            
            # Parse response - should have one item
            parent_path = str(PurePosixPath(path).parent)
            items = self._parse_propfind_response(response.text, parent_path)
            
            if items:
                # Find the matching item
                name = PurePosixPath(path).name
                for item in items:
                    if item.name == name:
                        return item
            
            # If no match, create from the raw response
            name = PurePosixPath(path).name
            return FileInfo(
                name=name,
                path=path,
                size=0,
                is_dir=True,  # Assume directory if we can't determine
                storage_type=StorageType.WEBDAV
            )
            
        except VFSNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error getting file info {path}: {e}")
            raise VFSError(f"Failed to get file info: {path}") from e
    
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
        try:
            if await self.exists(path):
                return True
            
            if parents:
                # Create parent directories
                parent = str(PurePosixPath(path).parent)
                if parent and parent != "/" and not await self.exists(parent):
                    await self.mkdir(parent, parents=True)
            
            url = self._full_url(path)
            response = await self._client.request("MKCOL", url)
            
            if response.status_code in (201, 405):  # Created or already exists
                return True
            
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}")
            raise VFSError(f"Failed to create directory: {path}") from e
    
    async def move(self, src: str, dst: str, overwrite: bool = True) -> bool:
        """Move file or directory"""
        try:
            src_url = self._full_url(src)
            dst_url = self._full_url(dst)
            
            # Ensure destination directory exists
            dst_parent = str(PurePosixPath(dst).parent)
            if not await self.exists(dst_parent):
                await self.mkdir(dst_parent, parents=True)
            
            headers = {"Destination": dst_url}
            if overwrite:
                headers["Overwrite"] = "T"
            else:
                headers["Overwrite"] = "F"
            
            response = await self._client.request("MOVE", src_url, headers=headers)
            
            if response.status_code in (201, 204):
                return True
            
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error(f"Error moving {src} -> {dst}: {e}")
            raise VFSError(f"Failed to move: {src} -> {dst}") from e
    
    async def copy(self, src: str, dst: str, overwrite: bool = True) -> bool:
        """Copy file or directory"""
        try:
            src_url = self._full_url(src)
            dst_url = self._full_url(dst)
            
            # Ensure destination directory exists
            dst_parent = str(PurePosixPath(dst).parent)
            if not await self.exists(dst_parent):
                await self.mkdir(dst_parent, parents=True)
            
            headers = {"Destination": dst_url}
            if overwrite:
                headers["Overwrite"] = "T"
            else:
                headers["Overwrite"] = "F"
            
            response = await self._client.request("COPY", src_url, headers=headers)
            
            if response.status_code in (201, 204):
                return True
            
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error(f"Error copying {src} -> {dst}: {e}")
            raise VFSError(f"Failed to copy: {src} -> {dst}") from e
    
    async def delete(self, path: str, recursive: bool = False) -> bool:
        """Delete file or directory"""
        try:
            url = self._full_url(path)
            response = await self._client.request("DELETE", url)
            
            if response.status_code in (200, 204, 404):  # Success or not found
                return True
            
            response.raise_for_status()
            return True
            
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
    
    async def close(self):
        """Close HTTP client"""
        await self._client.aclose()

