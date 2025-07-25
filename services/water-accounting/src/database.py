"""Database configuration and session management"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
import logging
from .config import get_settings

logger = logging.getLogger(__name__)

# Base class for models
Base = declarative_base()

# Database engines
engine = None
timescale_engine = None

# Session factories
AsyncSessionLocal = None
TimescaleSessionLocal = None

async def init_db():
    """Initialize database connections"""
    global engine, timescale_engine, AsyncSessionLocal, TimescaleSessionLocal
    
    settings = get_settings()
    
    try:
        # PostgreSQL for metadata
        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            poolclass=NullPool,
        )
        
        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("PostgreSQL database initialized successfully")
        
        # TimescaleDB for time-series data
        timescale_engine = create_async_engine(
            settings.TIMESCALE_URL,
            echo=settings.DEBUG,
            poolclass=NullPool,
        )
        
        TimescaleSessionLocal = async_sessionmaker(
            timescale_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Create TimescaleDB extensions and hypertables
        await init_timescale_tables()
        
        logger.info("TimescaleDB initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

async def init_timescale_tables():
    """Initialize TimescaleDB specific tables and extensions"""
    async with timescale_engine.begin() as conn:
        # Create TimescaleDB extension
        await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
        
        # Create time-series tables
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS flow_measurements (
                time TIMESTAMPTZ NOT NULL,
                gate_id TEXT NOT NULL,
                section_id TEXT NOT NULL,
                flow_rate_m3s DOUBLE PRECISION NOT NULL,
                cumulative_volume_m3 DOUBLE PRECISION,
                measurement_quality DOUBLE PRECISION,
                PRIMARY KEY (time, gate_id, section_id)
            );
        """)
        
        # Convert to hypertable
        await conn.execute("""
            SELECT create_hypertable(
                'flow_measurements', 
                'time',
                if_not_exists => TRUE
            );
        """)
        
        # Create continuous aggregates for efficiency calculations
        await conn.execute("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_flow_stats
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('1 hour', time) AS hour,
                gate_id,
                section_id,
                AVG(flow_rate_m3s) as avg_flow_rate,
                SUM(cumulative_volume_m3) as total_volume,
                COUNT(*) as measurement_count
            FROM flow_measurements
            GROUP BY hour, gate_id, section_id
            WITH NO DATA;
        """)
        
        # Create index for faster queries
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_flow_section_time 
            ON flow_measurements (section_id, time DESC);
        """)

async def close_db():
    """Close database connections"""
    global engine, timescale_engine
    
    if engine:
        await engine.dispose()
        logger.info("PostgreSQL connection closed")
    
    if timescale_engine:
        await timescale_engine.dispose()
        logger.info("TimescaleDB connection closed")

async def get_db():
    """Get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_timescale_db():
    """Get TimescaleDB session"""
    async with TimescaleSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()