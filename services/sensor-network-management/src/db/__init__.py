from .postgres import get_db, init_postgres
from .influxdb import get_influx_client, write_sensor_reading, query_sensor_data
from .redis import get_redis_client, cache_sensor_location, get_cached_locations

async def init_databases():
    """Initialize all database connections"""
    await init_postgres()
    # InfluxDB and Redis clients are initialized on demand
    
__all__ = [
    "get_db", "init_postgres",
    "get_influx_client", "write_sensor_reading", "query_sensor_data",
    "get_redis_client", "cache_sensor_location", "get_cached_locations",
    "init_databases"
]