"""
CMS API Client
Handles all interactions with MiBlock CMS API:
- Get list of components
- Download component Config, Format, Records
- Download component screenshots
- Authentication
"""
import httpx
from typing import Dict, List, Optional
import asyncio
from datetime import datetime

from src.config import settings


class CMSAPIError(Exception):
    """Raised when CMS API returns an error"""
    pass


class CMSClient:
    """
    Client for interacting with MiBlock CMS API
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        """
        Initialize CMS client
        
        Args:
            api_key: CMS API key (from settings if not provided)
            api_secret: CMS API secret (from settings if not provided)
            base_url: CMS API base URL (from settings if not provided)
        """
        self.api_key = api_key or settings.cms_api_key
        self.api_secret = api_secret or settings.cms_api_secret
        self.base_url = base_url or settings.cms_api_base_url
        self.rate_limit = settings.cms_rate_limit
        
        if not self.api_key or not self.base_url:
            raise ValueError("CMS API key and base URL are required")
        
        self.headers = {
            "X-API-Key": self.api_key,
            "X-API-Secret": self.api_secret,
            "Content-Type": "application/json"
        }
        
        # Rate limiting
        self._last_request_time = None
        self._request_interval = 60.0 / self.rate_limit
    
    async def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limits"""
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            if elapsed < self._request_interval:
                await asyncio.sleep(self._request_interval - elapsed)
        self._last_request_time = datetime.now()
    
    async def _request(
        self, 
        method: str, 
        endpoint: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None
    ) -> Dict:
        """
        Make API request with rate limiting
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            json: JSON body
            
        Returns:
            API response as dict
            
        Raises:
            CMSAPIError: If API returns an error
        """
        await self._wait_for_rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    json=json,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                error_msg = f"CMS API error: {e.response.status_code}"
                try:
                    error_data = e.response.json()
                    error_msg += f" - {error_data.get('error', error_data.get('message', ''))}"
                except:
                    pass
                raise CMSAPIError(error_msg) from e
            except httpx.RequestError as e:
                raise CMSAPIError(f"Failed to connect to CMS API: {str(e)}") from e
    
    async def get_components_list(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        active_only: bool = True
    ) -> List[Dict]:
        """
        Get list of all components from CMS
        
        Args:
            limit: Maximum number of components to return
            offset: Number of components to skip
            active_only: Only return active components
            
        Returns:
            List of component metadata
        """
        params = {
            "offset": offset,
            "active_only": active_only
        }
        if limit:
            params["limit"] = limit
        
        result = await self._request("GET", "/components", params=params)
        return result.get("components", [])
    
    async def get_component_config(self, component_id: int) -> Dict:
        """
        Get component config (MiBlockComponentConfig.json equivalent)
        
        Args:
            component_id: Component ID
            
        Returns:
            Component config data
        """
        return await self._request("GET", f"/components/{component_id}/config")
    
    async def get_component_format(self, component_id: int) -> Dict:
        """
        Get component format (MiBlockComponentFormat.json equivalent)
        
        Args:
            component_id: Component ID
            
        Returns:
            Component format data (includes FormatContent HTML)
        """
        return await self._request("GET", f"/components/{component_id}/format")
    
    async def get_component_records(
        self, 
        component_id: int,
        active_only: bool = True,
        limit_per_parent: int = 1
    ) -> Dict:
        """
        Get component records (MiBlockComponentRecords.json equivalent)
        
        NOTE: Only returns ONE ACTIVE SET of parent and child records,
        not all 500+ records!
        
        Args:
            component_id: Component ID
            active_only: Only return active records (Status=true)
            limit_per_parent: Maximum child records per parent (default 1)
            
        Returns:
            Component records data (filtered for training)
        """
        params = {
            "active_only": active_only,
            "limit_per_parent": limit_per_parent
        }
        return await self._request(
            "GET", 
            f"/components/{component_id}/records",
            params=params
        )
    
    async def get_component_screenshot(
        self, 
        component_id: int
    ) -> bytes:
        """
        Get component screenshot/design image
        
        Args:
            component_id: Component ID
            
        Returns:
            Screenshot image data as bytes
        """
        url = f"{self.base_url}/components/{component_id}/screenshot"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.content
            except httpx.HTTPStatusError as e:
                raise CMSAPIError(
                    f"Failed to get screenshot for component {component_id}: {e.response.status_code}"
                ) from e
    
    async def download_component(
        self, 
        component_id: int,
        include_screenshot: bool = True
    ) -> Dict:
        """
        Download all data for a single component
        
        Args:
            component_id: Component ID
            include_screenshot: Whether to download screenshot
            
        Returns:
            Dict containing all component data:
            {
                'component_id': int,
                'config': dict,
                'format': dict,
                'records': dict,
                'screenshot': bytes (if include_screenshot=True)
            }
        """
        # Download all data concurrently
        tasks = [
            self.get_component_config(component_id),
            self.get_component_format(component_id),
            self.get_component_records(component_id)
        ]
        
        if include_screenshot:
            tasks.append(self.get_component_screenshot(component_id))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                raise CMSAPIError(
                    f"Failed to download component {component_id}: {str(result)}"
                )
        
        component_data = {
            "component_id": component_id,
            "config": results[0],
            "format": results[1],
            "records": results[2]
        }
        
        if include_screenshot:
            component_data["screenshot"] = results[3]
        
        return component_data
    
    async def download_all_components(
        self,
        max_components: Optional[int] = None,
        include_screenshots: bool = True,
        batch_size: int = 10,
        progress_callback = None
    ) -> List[Dict]:
        """
        Download all components from CMS
        
        Args:
            max_components: Maximum number of components to download
            include_screenshots: Whether to download screenshots
            batch_size: Number of components to download concurrently
            progress_callback: Callback function(current, total, component_name)
            
        Returns:
            List of component data dicts
        """
        # Get list of all components
        components_list = await self.get_components_list(limit=max_components)
        total = len(components_list)
        
        if total == 0:
            return []
        
        all_components = []
        
        # Download in batches
        for i in range(0, total, batch_size):
            batch = components_list[i:i + batch_size]
            
            # Download batch concurrently
            tasks = [
                self.download_component(
                    comp["id"], 
                    include_screenshot=include_screenshots
                )
                for comp in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for j, result in enumerate(batch_results):
                comp = batch[j]
                
                if isinstance(result, Exception):
                    print(f"Error downloading component {comp['id']}: {result}")
                    continue
                
                # Add component name from list
                result["component_name"] = comp.get("name", f"Component {comp['id']}")
                all_components.append(result)
                
                # Progress callback
                if progress_callback:
                    progress_callback(
                        len(all_components),
                        total,
                        result["component_name"]
                    )
        
        return all_components
    
    async def check_component_updated(
        self, 
        component_id: int,
        last_check_timestamp: datetime
    ) -> bool:
        """
        Check if component has been updated since last check
        
        Args:
            component_id: Component ID
            last_check_timestamp: Last time we checked this component
            
        Returns:
            True if component has been updated
        """
        # This would depend on CMS API providing update timestamps
        # Placeholder implementation
        result = await self._request(
            "GET", 
            f"/components/{component_id}/metadata"
        )
        
        updated_at_str = result.get("updated_at")
        if not updated_at_str:
            return False
        
        updated_at = datetime.fromisoformat(updated_at_str)
        return updated_at > last_check_timestamp


# Example usage
if __name__ == "__main__":
    async def test_cms_client():
        """Test CMS client functionality"""
        client = CMSClient()
        
        # Test getting components list
        try:
            components = await client.get_components_list(limit=10)
            print(f"Found {len(components)} components")
            
            if components:
                # Test downloading first component
                first_comp = components[0]
                print(f"\nDownloading component: {first_comp['name']}")
                
                comp_data = await client.download_component(first_comp['id'])
                print(f"  Config keys: {list(comp_data['config'].keys())}")
                print(f"  Format keys: {list(comp_data['format'].keys())}")
                print(f"  Records keys: {list(comp_data['records'].keys())}")
                
        except Exception as e:
            print(f"Error: {e}")
    
    # Run test
    # asyncio.run(test_cms_client())



