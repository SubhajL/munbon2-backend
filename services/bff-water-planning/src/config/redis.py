"""Redis configuration for event publishing."""
import os
import logging
from typing import Optional
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisConfig:
    """Redis configuration and connection manager."""
    
    def __init__(self):
        self.publisher: Optional[redis.Redis] = None
        self.is_connected = False
        self.connection_attempts = 0
        self.max_retries = 10
        
    async def create_redis_client(self) -> Optional[redis.Redis]:
        """Create and configure Redis publisher client."""
        try:
            self.publisher = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', '6379')),
                password=os.getenv('REDIS_PASSWORD', None),
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                socket_keepalive_options={},
                retry_on_timeout=True,
                retry_on_error=[ConnectionError, TimeoutError]
            )
            
            # Test connection
            await self.publisher.ping()
            self.is_connected = True
            logger.info("Redis publisher connected successfully")
            return self.publisher
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.is_connected = False
            return None
    
    def get_redis_status(self) -> dict:
        """Get current Redis connection status."""
        return {
            'connected': self.is_connected,
            'connection_attempts': self.connection_attempts,
            'publisher_ready': self.publisher is not None
        }
    
    async def disconnect(self):
        """Disconnect Redis client."""
        if self.publisher:
            await self.publisher.close()
            self.publisher = None
            self.is_connected = False
            logger.info("Redis publisher disconnected")


# Singleton instance
redis_config = RedisConfig()