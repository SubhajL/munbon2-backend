from typing import List, Dict, Any, Optional
import asyncpg
import structlog
from uuid import UUID

from config import settings
from core.metrics import db_operations_total, db_operation_duration_seconds

logger = structlog.get_logger()


class PostgresClient:
    """Async PostgreSQL client for configuration and metadata"""
    
    def __init__(self):
        self.connection_url = settings.postgres_url
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self) -> None:
        """Connect to PostgreSQL"""
        try:
            self.pool = await asyncpg.create_pool(
                self.connection_url,
                min_size=5,
                max_size=15,
                command_timeout=60
            )
            
            # Create tables if they don't exist
            await self._create_tables()
            
        except Exception as e:
            logger.error("Failed to connect to PostgreSQL", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from PostgreSQL"""
        if self.pool:
            await self.pool.close()
    
    async def ping(self) -> bool:
        """Check if PostgreSQL is reachable"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error("PostgreSQL ping failed", error=str(e))
            return False
    
    async def _create_tables(self) -> None:
        """Create necessary tables"""
        async with self.pool.acquire() as conn:
            # Create sensor configuration table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS flow_sensors (
                    sensor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    sensor_type VARCHAR(50) NOT NULL,
                    location_id UUID NOT NULL,
                    channel_id VARCHAR(50) DEFAULT 'main',
                    manufacturer VARCHAR(100),
                    model VARCHAR(100),
                    serial_number VARCHAR(100),
                    installation_date DATE,
                    calibration_date DATE,
                    calibration_params JSONB,
                    status VARCHAR(20) DEFAULT 'active',
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            ''')
            
            # Create monitoring locations table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS monitoring_locations (
                    location_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    location_name VARCHAR(200) NOT NULL,
                    location_type VARCHAR(50) NOT NULL,
                    channel_id VARCHAR(50) DEFAULT 'main',
                    latitude DECIMAL(10,8),
                    longitude DECIMAL(11,8),
                    elevation DECIMAL(8,2),
                    upstream_locations UUID[],
                    downstream_locations UUID[],
                    hydraulic_params JSONB,
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            ''')
            
            # Create hydraulic models table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS hydraulic_models (
                    model_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    model_name VARCHAR(200) NOT NULL,
                    model_type VARCHAR(50) NOT NULL,
                    location_id UUID NOT NULL,
                    parameters JSONB NOT NULL,
                    version INTEGER DEFAULT 1,
                    is_active BOOLEAN DEFAULT TRUE,
                    accuracy_metrics JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            ''')
            
            # Create calibration history table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS calibration_history (
                    calibration_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    sensor_id UUID NOT NULL REFERENCES flow_sensors(sensor_id),
                    calibration_date TIMESTAMPTZ NOT NULL,
                    calibration_type VARCHAR(50) NOT NULL,
                    old_params JSONB,
                    new_params JSONB,
                    performed_by VARCHAR(100),
                    notes TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            ''')
            
            # Create indexes
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_flow_sensors_location 
                ON flow_sensors (location_id, status)
            ''')
            
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_monitoring_locations_type 
                ON monitoring_locations (location_type)
            ''')
            
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_hydraulic_models_location 
                ON hydraulic_models (location_id, is_active)
            ''')
    
    async def get_sensor_config(self, sensor_id: UUID) -> Optional[Dict[str, Any]]:
        """Get sensor configuration"""
        with db_operation_duration_seconds.labels(operation="query", database="postgres").time():
            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow('''
                        SELECT * FROM flow_sensors WHERE sensor_id = $1
                    ''', sensor_id)
                    
                    if row:
                        result = dict(row)
                        db_operations_total.labels(operation="query", database="postgres", status="success").inc()
                        return result
                    
                    return None
                    
            except Exception as e:
                logger.error("Failed to get sensor config", error=str(e))
                db_operations_total.labels(operation="query", database="postgres", status="error").inc()
                raise
    
    async def get_location_sensors(self, location_id: UUID) -> List[Dict[str, Any]]:
        """Get all sensors for a location"""
        with db_operation_duration_seconds.labels(operation="query", database="postgres").time():
            try:
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch('''
                        SELECT * FROM flow_sensors 
                        WHERE location_id = $1 AND status = 'active'
                        ORDER BY sensor_type, channel_id
                    ''', location_id)
                    
                    result = [dict(row) for row in rows]
                    db_operations_total.labels(operation="query", database="postgres", status="success").inc()
                    return result
                    
            except Exception as e:
                logger.error("Failed to get location sensors", error=str(e))
                db_operations_total.labels(operation="query", database="postgres", status="error").inc()
                raise
    
    async def get_monitoring_location(self, location_id: UUID) -> Optional[Dict[str, Any]]:
        """Get monitoring location details"""
        with db_operation_duration_seconds.labels(operation="query", database="postgres").time():
            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow('''
                        SELECT * FROM monitoring_locations WHERE location_id = $1
                    ''', location_id)
                    
                    if row:
                        result = dict(row)
                        db_operations_total.labels(operation="query", database="postgres", status="success").inc()
                        return result
                    
                    return None
                    
            except Exception as e:
                logger.error("Failed to get monitoring location", error=str(e))
                db_operations_total.labels(operation="query", database="postgres", status="error").inc()
                raise
    
    async def get_hydraulic_model(self, location_id: UUID) -> Optional[Dict[str, Any]]:
        """Get active hydraulic model for a location"""
        with db_operation_duration_seconds.labels(operation="query", database="postgres").time():
            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow('''
                        SELECT * FROM hydraulic_models 
                        WHERE location_id = $1 AND is_active = TRUE
                        ORDER BY version DESC
                        LIMIT 1
                    ''', location_id)
                    
                    if row:
                        result = dict(row)
                        db_operations_total.labels(operation="query", database="postgres", status="success").inc()
                        return result
                    
                    return None
                    
            except Exception as e:
                logger.error("Failed to get hydraulic model", error=str(e))
                db_operations_total.labels(operation="query", database="postgres", status="error").inc()
                raise
    
    async def update_sensor_calibration(
        self,
        sensor_id: UUID,
        calibration_params: Dict[str, Any],
        performed_by: str
    ) -> None:
        """Update sensor calibration parameters"""
        with db_operation_duration_seconds.labels(operation="update", database="postgres").time():
            try:
                async with self.pool.acquire() as conn:
                    async with conn.transaction():
                        # Get current params
                        old_params = await conn.fetchval('''
                            SELECT calibration_params FROM flow_sensors WHERE sensor_id = $1
                        ''', sensor_id)
                        
                        # Update sensor
                        await conn.execute('''
                            UPDATE flow_sensors 
                            SET calibration_params = $1,
                                calibration_date = NOW(),
                                updated_at = NOW()
                            WHERE sensor_id = $2
                        ''', calibration_params, sensor_id)
                        
                        # Record history
                        await conn.execute('''
                            INSERT INTO calibration_history (
                                sensor_id, calibration_date, calibration_type,
                                old_params, new_params, performed_by
                            ) VALUES ($1, NOW(), 'manual', $2, $3, $4)
                        ''', sensor_id, old_params, calibration_params, performed_by)
                        
                db_operations_total.labels(operation="update", database="postgres", status="success").inc()
                
            except Exception as e:
                logger.error("Failed to update sensor calibration", error=str(e))
                db_operations_total.labels(operation="update", database="postgres", status="error").inc()
                raise