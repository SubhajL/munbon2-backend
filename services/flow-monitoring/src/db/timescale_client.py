from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncpg
import structlog

from config import settings
from core.metrics import db_operations_total, db_operation_duration_seconds

logger = structlog.get_logger()


class TimescaleClient:
    """Async TimescaleDB client for aggregated hydraulic data"""
    
    def __init__(self):
        self.connection_url = settings.timescale_url
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self) -> None:
        """Connect to TimescaleDB"""
        try:
            self.pool = await asyncpg.create_pool(
                self.connection_url,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            
            # Create tables if they don't exist
            await self._create_tables()
            
        except Exception as e:
            logger.error("Failed to connect to TimescaleDB", error=str(e))
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from TimescaleDB"""
        if self.pool:
            await self.pool.close()
    
    async def ping(self) -> bool:
        """Check if TimescaleDB is reachable"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error("TimescaleDB ping failed", error=str(e))
            return False
    
    async def _create_tables(self) -> None:
        """Create necessary tables and hypertables"""
        async with self.pool.acquire() as conn:
            # Create flow aggregates table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS flow_aggregates (
                    time TIMESTAMPTZ NOT NULL,
                    location_id UUID NOT NULL,
                    channel_id VARCHAR(50) DEFAULT 'main',
                    avg_flow_rate DECIMAL(10,3),
                    max_flow_rate DECIMAL(10,3),
                    min_flow_rate DECIMAL(10,3),
                    total_volume DECIMAL(12,3),
                    water_level DECIMAL(8,3),
                    quality_score DECIMAL(3,2),
                    PRIMARY KEY (time, location_id, channel_id)
                )
            ''')
            
            # Convert to hypertable if not already
            await conn.execute('''
                SELECT create_hypertable(
                    'flow_aggregates', 
                    'time',
                    if_not_exists => TRUE,
                    chunk_time_interval => INTERVAL '1 day'
                )
            ''')
            
            # Create water balance table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS water_balance (
                    time TIMESTAMPTZ NOT NULL,
                    segment_id UUID NOT NULL,
                    inflow_volume DECIMAL(12,3),
                    outflow_volume DECIMAL(12,3),
                    balance_volume DECIMAL(12,3),
                    loss_volume DECIMAL(12,3),
                    efficiency_percent DECIMAL(5,2),
                    PRIMARY KEY (time, segment_id)
                )
            ''')
            
            # Convert to hypertable if not already
            await conn.execute('''
                SELECT create_hypertable(
                    'water_balance', 
                    'time',
                    if_not_exists => TRUE,
                    chunk_time_interval => INTERVAL '1 day'
                )
            ''')
            
            # Create anomalies table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS flow_anomalies (
                    time TIMESTAMPTZ NOT NULL,
                    location_id UUID NOT NULL,
                    anomaly_type VARCHAR(50) NOT NULL,
                    severity VARCHAR(20) NOT NULL,
                    detected_value DECIMAL(10,3),
                    expected_value DECIMAL(10,3),
                    deviation DECIMAL(10,3),
                    description TEXT,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolved_at TIMESTAMPTZ,
                    PRIMARY KEY (time, location_id, anomaly_type)
                )
            ''')
            
            # Create indexes
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_flow_aggregates_location_time 
                ON flow_aggregates (location_id, time DESC)
            ''')
            
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_water_balance_segment_time 
                ON water_balance (segment_id, time DESC)
            ''')
            
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_flow_anomalies_unresolved 
                ON flow_anomalies (location_id, resolved) 
                WHERE resolved = FALSE
            ''')
    
    async def insert_flow_aggregate(self, data: Dict[str, Any]) -> None:
        """Insert aggregated flow data"""
        with db_operation_duration_seconds.labels(operation="insert", database="timescale").time():
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute('''
                        INSERT INTO flow_aggregates (
                            time, location_id, channel_id, avg_flow_rate,
                            max_flow_rate, min_flow_rate, total_volume,
                            water_level, quality_score
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (time, location_id, channel_id) 
                        DO UPDATE SET
                            avg_flow_rate = EXCLUDED.avg_flow_rate,
                            max_flow_rate = EXCLUDED.max_flow_rate,
                            min_flow_rate = EXCLUDED.min_flow_rate,
                            total_volume = EXCLUDED.total_volume,
                            water_level = EXCLUDED.water_level,
                            quality_score = EXCLUDED.quality_score
                    ''', 
                        data['time'], data['location_id'], data.get('channel_id', 'main'),
                        data['avg_flow_rate'], data['max_flow_rate'], data['min_flow_rate'],
                        data['total_volume'], data['water_level'], data.get('quality_score', 1.0)
                    )
                    
                db_operations_total.labels(operation="insert", database="timescale", status="success").inc()
                
            except Exception as e:
                logger.error("Failed to insert flow aggregate", error=str(e))
                db_operations_total.labels(operation="insert", database="timescale", status="error").inc()
                raise
    
    async def get_flow_history(
        self,
        location_id: str,
        start_time: datetime,
        end_time: datetime,
        interval: str = '1 hour'
    ) -> List[Dict[str, Any]]:
        """Get historical flow data with time bucketing"""
        with db_operation_duration_seconds.labels(operation="query", database="timescale").time():
            try:
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch('''
                        SELECT 
                            time_bucket($1::interval, time) AS bucket,
                            location_id,
                            channel_id,
                            AVG(avg_flow_rate) AS avg_flow_rate,
                            MAX(max_flow_rate) AS max_flow_rate,
                            MIN(min_flow_rate) AS min_flow_rate,
                            SUM(total_volume) AS total_volume,
                            AVG(water_level) AS avg_water_level
                        FROM flow_aggregates
                        WHERE location_id = $2
                            AND time >= $3
                            AND time <= $4
                        GROUP BY bucket, location_id, channel_id
                        ORDER BY bucket DESC
                    ''', interval, location_id, start_time, end_time)
                    
                    result = [dict(row) for row in rows]
                    
                db_operations_total.labels(operation="query", database="timescale", status="success").inc()
                return result
                
            except Exception as e:
                logger.error("Failed to get flow history", error=str(e))
                db_operations_total.labels(operation="query", database="timescale", status="error").inc()
                raise
    
    async def insert_water_balance(self, data: Dict[str, Any]) -> None:
        """Insert water balance data"""
        with db_operation_duration_seconds.labels(operation="insert", database="timescale").time():
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute('''
                        INSERT INTO water_balance (
                            time, segment_id, inflow_volume, outflow_volume,
                            balance_volume, loss_volume, efficiency_percent
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ''',
                        data['time'], data['segment_id'], data['inflow_volume'],
                        data['outflow_volume'], data['balance_volume'],
                        data['loss_volume'], data['efficiency_percent']
                    )
                    
                db_operations_total.labels(operation="insert", database="timescale", status="success").inc()
                
            except Exception as e:
                logger.error("Failed to insert water balance", error=str(e))
                db_operations_total.labels(operation="insert", database="timescale", status="error").inc()
                raise
    
    async def record_anomaly(self, anomaly: Dict[str, Any]) -> None:
        """Record a detected anomaly"""
        with db_operation_duration_seconds.labels(operation="insert", database="timescale").time():
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute('''
                        INSERT INTO flow_anomalies (
                            time, location_id, anomaly_type, severity,
                            detected_value, expected_value, deviation, description
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ''',
                        anomaly['time'], anomaly['location_id'], anomaly['anomaly_type'],
                        anomaly['severity'], anomaly['detected_value'], anomaly['expected_value'],
                        anomaly['deviation'], anomaly.get('description', '')
                    )
                    
                db_operations_total.labels(operation="insert", database="timescale", status="success").inc()
                
            except Exception as e:
                logger.error("Failed to record anomaly", error=str(e))
                db_operations_total.labels(operation="insert", database="timescale", status="error").inc()
                raise