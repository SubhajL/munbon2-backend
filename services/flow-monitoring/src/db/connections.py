import structlog
from typing import Dict, Any

from config import settings
from .influxdb_client import InfluxDBClient
from .timescale_client import TimescaleClient
from .postgres_client import PostgresClient
from .redis_client import RedisClient

logger = structlog.get_logger()


class DatabaseManager:
    """Manages all database connections for the service"""
    
    def __init__(self):
        self.influxdb = InfluxDBClient()
        self.timescale = TimescaleClient()
        self.postgres = PostgresClient()
        self.redis = RedisClient()
        
    async def connect_all(self) -> None:
        """Connect to all databases"""
        try:
            # Connect to InfluxDB
            await self.influxdb.connect()
            logger.info("Connected to InfluxDB")
            
            # Connect to TimescaleDB
            await self.timescale.connect()
            logger.info("Connected to TimescaleDB")
            
            # Connect to PostgreSQL
            await self.postgres.connect()
            logger.info("Connected to PostgreSQL")
            
            # Connect to Redis
            await self.redis.connect()
            logger.info("Connected to Redis")
            
        except Exception as e:
            logger.error("Failed to connect to databases", error=str(e))
            raise
    
    async def disconnect_all(self) -> None:
        """Disconnect from all databases"""
        try:
            await self.influxdb.disconnect()
            await self.timescale.disconnect()
            await self.postgres.disconnect()
            await self.redis.disconnect()
            logger.info("Disconnected from all databases")
        except Exception as e:
            logger.error("Error disconnecting from databases", error=str(e))
    
    async def check_health(self) -> Dict[str, bool]:
        """Check health of all database connections"""
        health_status = {}
        
        try:
            health_status["influxdb"] = await self.influxdb.ping()
        except:
            health_status["influxdb"] = False
            
        try:
            health_status["timescale"] = await self.timescale.ping()
        except:
            health_status["timescale"] = False
            
        try:
            health_status["postgres"] = await self.postgres.ping()
        except:
            health_status["postgres"] = False
            
        try:
            health_status["redis"] = await self.redis.ping()
        except:
            health_status["redis"] = False
            
        return health_status