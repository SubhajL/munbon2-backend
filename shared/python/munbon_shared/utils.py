"""Utility functions and classes for Munbon services."""

import asyncio
import time
from typing import TypeVar, Callable, Optional, Any, Dict
from enum import Enum
from functools import wraps
from datetime import datetime, timedelta

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryCallState
)

from munbon_shared.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def retry_async(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    exception_types: tuple = (Exception,)
) -> Callable:
    """
    Decorator for retrying async functions with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        exception_types: Tuple of exception types to retry on
    """
    def log_retry(retry_state: RetryCallState) -> None:
        """Log retry attempts."""
        logger.warning(
            "Retrying function",
            function=retry_state.fn.__name__,
            attempt=retry_state.attempt_number,
            wait_time=retry_state.next_action.sleep if retry_state.next_action else 0
        )
    
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=min_wait, max=max_wait),
        retry=retry_if_exception_type(exception_types),
        after=log_retry,
        reraise=True
    )


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Circuit breaker implementation for fault tolerance.
    
    The circuit breaker prevents cascading failures by stopping
    requests to a failing service until it recovers.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state
    
    def _is_recovery_time(self) -> bool:
        """Check if it's time to attempt recovery."""
        if self._last_failure_time is None:
            return True
        
        recovery_time = self._last_failure_time + timedelta(
            seconds=self.recovery_timeout
        )
        return datetime.utcnow() >= recovery_time
    
    async def __aenter__(self):
        """Context manager entry."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._is_recovery_time():
                    logger.info("Circuit breaker attempting recovery")
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise Exception("Circuit breaker is OPEN")
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        async with self._lock:
            if exc_type is None:
                # Success - reset failure count
                if self._state == CircuitState.HALF_OPEN:
                    logger.info("Circuit breaker recovered, closing circuit")
                    self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._last_failure_time = None
            elif issubclass(exc_type, self.expected_exception):
                # Expected failure - increment count
                self._failure_count += 1
                self._last_failure_time = datetime.utcnow()
                
                if self._failure_count >= self.failure_threshold:
                    logger.error(
                        "Circuit breaker threshold exceeded, opening circuit",
                        failures=self._failure_count
                    )
                    self._state = CircuitState.OPEN
                elif self._state == CircuitState.HALF_OPEN:
                    logger.warning("Circuit breaker recovery failed, reopening")
                    self._state = CircuitState.OPEN
        
        return False  # Don't suppress the exception
    
    def call(self, func: Callable) -> Callable:
        """Decorator for protecting functions with circuit breaker."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with self:
                return await func(*args, **kwargs)
        
        return wrapper


class SimpleCache:
    """Simple in-memory cache with TTL support."""
    
    def __init__(self, default_ttl: int = 300):
        """
        Initialize cache.
        
        Args:
            default_ttl: Default TTL in seconds
        """
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if time.time() < expiry:
                    return value
                else:
                    # Expired - remove from cache
                    del self._cache[key]
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """Set value in cache with TTL."""
        ttl = ttl or self._default_ttl
        expiry = time.time() + ttl
        
        async with self._lock:
            self._cache[key] = (value, expiry)
    
    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        async with self._lock:
            self._cache.pop(key, None)
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
    
    async def cleanup(self) -> None:
        """Remove expired entries."""
        current_time = time.time()
        async with self._lock:
            expired_keys = [
                key for key, (_, expiry) in self._cache.items()
                if current_time >= expiry
            ]
            for key in expired_keys:
                del self._cache[key]
    
    def cached(self, ttl: Optional[int] = None) -> Callable:
        """Decorator for caching function results."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Create cache key from function name and arguments
                key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
                
                # Try to get from cache
                result = await self.get(key)
                if result is not None:
                    return result
                
                # Call function and cache result
                result = await func(*args, **kwargs)
                await self.set(key, result, ttl)
                
                return result
            
            return wrapper
        
        return decorator