"""
Figma API Client
Handles all interactions with Figma API:
- Parse Figma URLs
- Detect page vs node URLs
- Get file structure
- Get screenshots
- Extract metadata
"""
import re
import httpx
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs
import asyncio
from datetime import datetime

from src.config import settings


class FigmaAPIError(Exception):
    """Raised when Figma API returns an error"""
    pass


class FigmaClient:
    """
    Client for interacting with Figma API
    """
    
    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize Figma client
        
        Args:
            api_token: Figma personal access token (from settings if not provided)
        """
        self.api_token = api_token or settings.figma_api_token
        self.base_url = settings.figma_api_base_url
        self.rate_limit = settings.figma_rate_limit
        
        if not self.api_token:
            raise ValueError("Figma API token is required")
        
        self.headers = {
            "X-Figma-Token": self.api_token
        }
        
        # Rate limiting
        self._last_request_time = None
        self._request_interval = 60.0 / self.rate_limit  # seconds between requests
    
    async def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limits"""
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            if elapsed < self._request_interval:
                await asyncio.sleep(self._request_interval - elapsed)
        self._last_request_time = datetime.now()
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        Make API request with rate limiting
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request parameters
            
        Returns:
            API response as dict
            
        Raises:
            FigmaAPIError: If API returns an error
        """
        await self._wait_for_rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    timeout=30.0,
                    **kwargs
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                error_msg = f"Figma API error: {e.response.status_code}"
                try:
                    error_data = e.response.json()
                    error_msg += f" - {error_data.get('err', error_data.get('message', ''))}"
                except:
                    pass
                raise FigmaAPIError(error_msg) from e
            except httpx.RequestError as e:
                raise FigmaAPIError(f"Failed to connect to Figma API: {str(e)}") from e
    
    def parse_figma_url(self, url: str) -> Dict[str, str]:
        """
        Parse Figma URL to extract file ID and node ID
        
        Args:
            url: Figma URL
            
        Returns:
            Dict with file_id and node_id (node_id may be None)
            
        Examples:
            https://www.figma.com/file/ABC123/Design?node-id=123:456
            https://www.figma.com/design/ABC123/Design?node-id=123-456
            https://www.figma.com/file/ABC123/Design
        """
        parsed = urlparse(url)
        
        # Extract file ID from path
        # Path format: /file/{file_id}/{name} or /design/{file_id}/{name}
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) < 2:
            raise ValueError(f"Invalid Figma URL format: {url}")
        
        file_id = path_parts[1]
        
        # Extract node ID from query params if present
        query_params = parse_qs(parsed.query)
        node_id = query_params.get('node-id', [None])[0]
        
        # Handle different node-id formats (123:456 or 123-456)
        if node_id:
            node_id = node_id.replace('-', ':')
        
        return {
            "file_id": file_id,
            "node_id": node_id,
            "is_node_url": node_id is not None
        }
    
    async def get_file(self, file_id: str) -> Dict:
        """
        Get file metadata and structure
        
        Args:
            file_id: Figma file ID
            
        Returns:
            File data including all pages and nodes
        """
        return await self._request("GET", f"/files/{file_id}")
    
    async def get_node(self, file_id: str, node_id: str) -> Dict:
        """
        Get specific node data
        
        Args:
            file_id: Figma file ID
            node_id: Node ID (format: 123:456)
            
        Returns:
            Node data
        """
        params = {"ids": node_id}
        result = await self._request("GET", f"/files/{file_id}/nodes", params=params)
        return result.get("nodes", {}).get(node_id, {})
    
    async def get_sections(self, file_id: str, node_id: Optional[str] = None) -> List[Dict]:
        """
        Get list of sections/frames from file or specific node
        
        Args:
            file_id: Figma file ID
            node_id: Optional node ID (if None, gets all top-level frames)
            
        Returns:
            List of section dictionaries with metadata
        """
        if node_id:
            # Get specific node
            node = await self.get_node(file_id, node_id)
            if not node:
                return []
            return [self._extract_section_info(node, file_id, node_id)]
        else:
            # Get all top-level frames from file
            file_data = await self.get_file(file_id)
            sections = []
            
            # Iterate through pages
            document = file_data.get("document", {})
            for page in document.get("children", []):
                if page.get("type") == "CANVAS":
                    # Get top-level frames on this page
                    for child in page.get("children", []):
                        if child.get("type") in ["FRAME", "SECTION", "COMPONENT"]:
                            section_info = self._extract_section_info(
                                child, 
                                file_id, 
                                child.get("id")
                            )
                            sections.append(section_info)
            
            return sections
    
    def _extract_section_info(self, node: Dict, file_id: str, node_id: str) -> Dict:
        """
        Extract relevant section information from node
        
        Args:
            node: Node data from Figma API
            file_id: File ID
            node_id: Node ID
            
        Returns:
            Section info dict
        """
        bounds = node.get("absoluteBoundingBox", {})
        
        return {
            "node_id": node_id,
            "file_id": file_id,
            "name": node.get("name", "Unnamed Section"),
            "type": node.get("type", "FRAME"),
            "width": bounds.get("width", 0),
            "height": bounds.get("height", 0),
            "x": bounds.get("x", 0),
            "y": bounds.get("y", 0),
            "background_color": node.get("backgroundColor"),
            "node_data": node  # Full node data for further processing
        }
    
    async def get_screenshot(
        self, 
        file_id: str, 
        node_id: str, 
        scale: float = 2.0,
        format: str = "png"
    ) -> bytes:
        """
        Get screenshot of a specific node
        
        Args:
            file_id: Figma file ID
            node_id: Node ID
            scale: Scale factor (1.0, 2.0, etc.)
            format: Image format (png, jpg, svg)
            
        Returns:
            Screenshot image data as bytes
        """
        # Get image URL from Figma
        params = {
            "ids": node_id,
            "format": format,
            "scale": scale
        }
        
        result = await self._request("GET", f"/images/{file_id}", params=params)
        
        image_url = result.get("images", {}).get(node_id)
        if not image_url:
            raise FigmaAPIError(f"No image URL returned for node {node_id}")
        
        # Download the image
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url, timeout=30.0)
            response.raise_for_status()
            return response.content
    
    async def process_figma_url(
        self, 
        url: str
    ) -> Tuple[List[Dict], List[bytes]]:
        """
        Process Figma URL and return sections with screenshots
        
        Args:
            url: Figma URL (page or node)
            
        Returns:
            Tuple of (sections_list, screenshots_list)
            
        Example:
            sections, screenshots = await client.process_figma_url(url)
            for section, screenshot in zip(sections, screenshots):
                print(f"Section: {section['name']}")
                # Save screenshot...
        """
        # Parse URL
        parsed = self.parse_figma_url(url)
        file_id = parsed["file_id"]
        node_id = parsed.get("node_id")
        
        # Get sections
        sections = await self.get_sections(file_id, node_id)
        
        if not sections:
            raise FigmaAPIError("No sections found in the provided URL")
        
        # Get screenshots for all sections
        screenshots = []
        for section in sections:
            try:
                screenshot = await self.get_screenshot(
                    file_id=section["file_id"],
                    node_id=section["node_id"]
                )
                screenshots.append(screenshot)
            except Exception as e:
                print(f"Warning: Failed to get screenshot for {section['name']}: {e}")
                screenshots.append(None)
        
        return sections, screenshots
    
    async def get_file_metadata(self, file_id: str) -> Dict:
        """
        Get file metadata (name, version, last modified, etc.)
        
        Args:
            file_id: Figma file ID
            
        Returns:
            File metadata
        """
        file_data = await self.get_file(file_id)
        return {
            "name": file_data.get("name"),
            "version": file_data.get("version"),
            "last_modified": file_data.get("lastModified"),
            "thumbnail_url": file_data.get("thumbnailUrl"),
            "document": file_data.get("document", {})
        }


# Example usage and testing
if __name__ == "__main__":
    async def test_figma_client():
        """Test Figma client functionality"""
        client = FigmaClient()
        
        # Test URL parsing
        test_urls = [
            "https://www.figma.com/file/ABC123/Design",
            "https://www.figma.com/file/ABC123/Design?node-id=123:456",
            "https://www.figma.com/design/XYZ789/MyDesign?node-id=1-2"
        ]
        
        for url in test_urls:
            try:
                parsed = client.parse_figma_url(url)
                print(f"URL: {url}")
                print(f"  File ID: {parsed['file_id']}")
                print(f"  Node ID: {parsed['node_id']}")
                print(f"  Is Node URL: {parsed['is_node_url']}")
                print()
            except Exception as e:
                print(f"Error parsing {url}: {e}")
    
    # Run test
    # asyncio.run(test_figma_client())


