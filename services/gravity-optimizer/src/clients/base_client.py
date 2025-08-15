"""Base client for inter-service communication with circuit breaker and retry logic"""

import asyncio
import logging
from typing import Optional, Dict, Any, TypeVar, Type
from datetime import datetime, timedelta
import httpx
from pydantic import BaseModel
from enum import Enum
import random

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker pattern implementation"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try again"""
        return (
            self.last_failure_time and
            datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout)
        )
    
    def _on_success(self):
        """Reset circuit breaker on successful call"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = None
    
    def _on_failure(self):
        """Increment failure count and possibly open circuit"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")


class BaseServiceClient:
    """Base class for service clients with retry and circuit breaker"""
    
    def __init__(
        self,
        service_name: str,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        circuit_breaker_enabled: bool = True
    ):
        self.service_name = service_name
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.circuit_breaker = CircuitBreaker() if circuit_breaker_enabled else None
        self._client: Optional[httpx.AsyncClient] = None
        self._headers = {
            'Content-Type': 'application/json',
            'X-Service-Name': 'gravity-optimizer',
            'X-Request-ID': None  # Will be set per request
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
    
    async def connect(self):
        """Initialize HTTP client"""
        if not self._client:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
            logger.info(f"Connected to {self.service_name} at {self.base_url}")
    
    async def disconnect(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info(f"Disconnected from {self.service_name}")
    
    def _get_request_id(self) -> str:
        """Generate unique request ID"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_suffix = ''.join(random.choices('0123456789abcdef', k=8))
        return f"gravity-{timestamp}-{random_suffix}"
    
    async def _execute_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute HTTP request with retry logic"""
        if not self._client:
            await self.connect()
        
        # Set request ID
        self._headers['X-Request-ID'] = self._get_request_id()
        kwargs.setdefault('headers', {}).update(self._headers)
        
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                if self.circuit_breaker:
                    response = await self.circuit_breaker.call(
                        self._client.request, method, url, **kwargs
                    )
                else:
                    response = await self._client.request(method, url, **kwargs)
                
                response.raise_for_status()
                return response
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500:
                    # Don't retry client errors
                    logger.error(f"{self.service_name} client error: {e}")
                    raise
                last_exception = e
                
            except (httpx.RequestError, httpx.TimeoutException) as e:
                last_exception = e
                
            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(
                    f"{self.service_name} request failed (attempt {attempt + 1}/{self.max_retries}), "
                    f"retrying in {delay}s: {last_exception}"
                )
                await asyncio.sleep(delay)
        
        logger.error(f"{self.service_name} request failed after {self.max_retries} attempts")
        raise last_exception
    
    async def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute GET request"""
        url = f"{self.base_url}{endpoint}"
        response = await self._execute_with_retry('GET', url, params=params)
        return response.json()
    
    async def post(
        self, 
        endpoint: str, 
        data: Optional[Dict] = None, 
        model: Optional[BaseModel] = None
    ) -> Dict[str, Any]:
        """Execute POST request"""
        url = f"{self.base_url}{endpoint}"
        
        if model:
            json_data = model.model_dump(exclude_unset=True)
        else:
            json_data = data
        
        response = await self._execute_with_retry('POST', url, json=json_data)
        return response.json()
    
    async def put(
        self, 
        endpoint: str, 
        data: Optional[Dict] = None,
        model: Optional[BaseModel] = None
    ) -> Dict[str, Any]:
        """Execute PUT request"""
        url = f"{self.base_url}{endpoint}"
        
        if model:
            json_data = model.model_dump(exclude_unset=True)
        else:
            json_data = data
            
        response = await self._execute_with_retry('PUT', url, json=json_data)
        return response.json()
    
    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """Execute DELETE request"""
        url = f"{self.base_url}{endpoint}"
        response = await self._execute_with_retry('DELETE', url)
        return response.json()
    
    async def health_check(self) -> bool:
        """Check if service is healthy"""
        try:
            response = await self.get('/health')
            return response.get('status') == 'healthy'
        except Exception as e:
            logger.warning(f"{self.service_name} health check failed: {e}")
            return False
    
    def parse_response(self, response: Dict[str, Any], model: Type[T]) -> T:
        """Parse response into Pydantic model"""
        return model(**response)