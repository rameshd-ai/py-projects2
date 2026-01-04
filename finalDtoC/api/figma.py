"""
Figma API Client
Handles downloading screenshots from Figma URLs
"""
import requests
import re
import os
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs


class FigmaClient:
    """Client for interacting with Figma API"""
    
    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize Figma client
        
        Args:
            access_token: Figma API access token (from .env)
        """
        self.access_token = access_token or os.getenv('FIGMA_ACCESS_TOKEN')
        self.base_url = 'https://api.figma.com/v1'
        
        if not self.access_token:
            raise ValueError("FIGMA_ACCESS_TOKEN not found in environment variables")
    
    def parse_figma_url(self, url: str) -> Tuple[str, Optional[str]]:
        """
        Parse Figma URL to extract file_id and node_id
        
        Args:
            url: Figma URL (e.g., https://www.figma.com/file/abc123/Design?node-id=1%3A2)
        
        Returns:
            Tuple of (file_id, node_id)
        """
        # Pattern: https://www.figma.com/file/{file_id}/{name}?node-id={node_id}
        pattern = r'figma\.com/file/([^/]+)'
        match = re.search(pattern, url)
        
        if not match:
            raise ValueError(f"Invalid Figma URL: {url}")
        
        file_id = match.group(1)
        
        # Extract node_id from query parameters
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        node_id = query_params.get('node-id', [None])[0]
        
        return file_id, node_id
    
    def get_screenshot(self, figma_url: str, output_path: Optional[str] = None) -> str:
        """
        Download screenshot from Figma
        
        Args:
            figma_url: Figma URL of the design
            output_path: Optional path to save screenshot
        
        Returns:
            Path to saved screenshot
        """
        file_id, node_id = self.parse_figma_url(figma_url)
        
        # Build API endpoint
        endpoint = f"{self.base_url}/images/{file_id}"
        params = {
            'format': 'png',
            'scale': 2,  # High resolution
        }
        
        if node_id:
            params['ids'] = node_id
        
        headers = {
            'X-Figma-Token': self.access_token
        }
        
        # Get image URL from Figma API
        response = requests.get(endpoint, params=params, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        image_url = data.get('images', {}).get(node_id or file_id)
        
        if not image_url:
            raise ValueError("Could not get image URL from Figma API")
        
        # Download the actual image
        img_response = requests.get(image_url)
        img_response.raise_for_status()
        
        # Save screenshot
        if not output_path:
            os.makedirs('screenshots', exist_ok=True)
            output_path = f"screenshots/figma_{file_id}_{node_id or 'all'}.png"
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'wb') as f:
            f.write(img_response.content)
        
        return output_path

