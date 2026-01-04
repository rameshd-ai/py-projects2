"""
CMS API Client
Handles downloading components from CMS
"""
import requests
import os
import json
from typing import List, Dict, Optional


class CMSClient:
    """Client for interacting with CMS API"""
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize CMS client
        
        Args:
            base_url: CMS API base URL (from .env)
            api_key: CMS API key (from .env)
        """
        self.base_url = base_url or os.getenv('CMS_BASE_URL', 'https://api.cms.example.com')
        self.api_key = api_key or os.getenv('CMS_API_KEY')
        
        if not self.api_key:
            raise ValueError("CMS_API_KEY not found in environment variables")
    
    def get_components(self) -> List[Dict]:
        """
        Get list of all components from CMS
        
        Returns:
            List of component metadata
        """
        endpoint = f"{self.base_url}/components"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    def get_component(self, component_id: str) -> Dict:
        """
        Get a specific component by ID
        
        Args:
            component_id: Component ID
        
        Returns:
            Component data including Config, Format, and Records JSON
        """
        endpoint = f"{self.base_url}/components/{component_id}"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    def download_component_files(self, component_id: str, output_dir: str = 'components') -> Dict[str, str]:
        """
        Download all files for a component (Config, Format, Records, Screenshot)
        
        Args:
            component_id: Component ID
            output_dir: Directory to save files
        
        Returns:
            Dictionary with paths to downloaded files
        """
        component = self.get_component(component_id)
        
        os.makedirs(output_dir, exist_ok=True)
        
        files = {}
        
        # Download Config JSON
        if 'config' in component:
            config_path = f"{output_dir}/{component_id}_config.json"
            with open(config_path, 'w') as f:
                json.dump(component['config'], f, indent=2)
            files['config'] = config_path
        
        # Download Format JSON
        if 'format' in component:
            format_path = f"{output_dir}/{component_id}_format.json"
            with open(format_path, 'w') as f:
                json.dump(component['format'], f, indent=2)
            files['format'] = format_path
        
        # Download Records JSON
        if 'records' in component:
            records_path = f"{output_dir}/{component_id}_records.json"
            with open(records_path, 'w') as f:
                json.dump(component['records'], f, indent=2)
            files['records'] = records_path
        
        # Download Screenshot if available
        if 'screenshot_url' in component:
            screenshot_url = component['screenshot_url']
            screenshot_path = f"{output_dir}/{component_id}_screenshot.png"
            img_response = requests.get(screenshot_url)
            img_response.raise_for_status()
            with open(screenshot_path, 'wb') as f:
                f.write(img_response.content)
            files['screenshot'] = screenshot_path
        
        return files

