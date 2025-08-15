import httpx
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

from ...core.logger import get_logger
from ...core.config import settings

logger = get_logger(__name__)


class BaseServiceClient(ABC):
    """Base class for service clients"""
    
    def __init__(self, base_url: str, service_name: str):
        self.base_url = base_url.rstrip("/")
        self.service_name = service_name
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy initialization of HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._get_default_headers(),
            )
        return self._client
    
    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for requests"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Service-Name": settings.service_name,
        }
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request with error handling"""
        try:
            response = await self.client.request(
                method=method,
                url=endpoint,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"{self.service_name} request failed: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"{self.service_name} request error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling {self.service_name}: {str(e)}")
            raise
    
    async def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request"""
        return await self._make_request("GET", endpoint, params=params)
    
    async def post(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make POST request"""
        return await self._make_request("POST", endpoint, json=data)
    
    async def put(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make PUT request"""
        return await self._make_request("PUT", endpoint, json=data)
    
    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make DELETE request"""
        return await self._make_request("DELETE", endpoint)
    
    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()