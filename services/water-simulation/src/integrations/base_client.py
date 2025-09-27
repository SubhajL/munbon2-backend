"""
Base client for service communication
"""

import httpx
import logging
from typing import Dict, Any, Optional
from src.config import get_settings

logger = logging.getLogger(__name__)


class BaseServiceClient:
    """Base class for service clients with common functionality"""
    
    def __init__(self, base_url: str, service_name: str):
        self.base_url = base_url.rstrip('/')
        self.service_name = service_name
        self.settings = get_settings()
        self._client = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(30.0),
                headers={"User-Agent": f"{self.settings.service_name}/v{self.settings.version}"}
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make an HTTP request with error handling"""
        try:
            logger.debug(f"Making {method} request to {self.service_name}: {endpoint}")
            
            response = await self.client.request(
                method=method,
                url=endpoint,
                params=params,
                json=json_data,
                **kwargs
            )
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from {self.service_name}: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error to {self.service_name}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling {self.service_name}: {str(e)}")
            raise
    
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a GET request"""
        return await self._request("GET", endpoint, params=params)
    
    async def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a POST request"""
        return await self._request("POST", endpoint, json_data=data)
    
    async def put(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a PUT request"""
        return await self._request("PUT", endpoint, json_data=data)
    
    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make a DELETE request"""
        return await self._request("DELETE", endpoint)
    
    async def health_check(self) -> bool:
        """Check if the service is healthy"""
        try:
            await self.get("/health")
            return True
        except Exception:
            return False