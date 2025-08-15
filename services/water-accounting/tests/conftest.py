"""Pytest configuration and fixtures"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from httpx import AsyncClient

from src.database import Base
from src.main import app
from src.config import Settings, get_settings

# Test database URLs
TEST_DATABASE_URL = "postgresql+asyncpg://test_user:test_pass@localhost:5432/test_water_accounting"
TEST_TIMESCALE_URL = "postgresql+asyncpg://test_user:test_pass@localhost:5433/test_timescale"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Override settings for testing"""
    settings = Settings(
        DATABASE_URL=TEST_DATABASE_URL,
        TIMESCALE_URL=TEST_TIMESCALE_URL,
        SERVICE_PORT=3024,
        DEBUG=True,
        SENSOR_DATA_SERVICE_URL="http://localhost:3003",
        GIS_SERVICE_URL="http://localhost:3007",
        WEATHER_SERVICE_URL="http://localhost:3008",
        SCADA_SERVICE_URL="http://localhost:3023"
    )
    return settings

@pytest.fixture(scope="session")
async def test_db_engine(test_settings):
    """Create test database engine"""
    engine = create_async_engine(
        test_settings.DATABASE_URL,
        poolclass=NullPool,
        echo=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()

@pytest.fixture
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for tests"""
    async_session = sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
def override_get_settings(test_settings):
    """Override settings dependency"""
    def _override():
        return test_settings
    
    app.dependency_overrides[get_settings] = _override
    yield
    app.dependency_overrides.clear()

@pytest.fixture
async def client(override_get_settings) -> AsyncGenerator[AsyncClient, None]:
    """Create test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def sample_section(db_session):
    """Create sample section for testing"""
    from src.models import Section
    
    section = Section(
        id="SEC-TEST-001",
        name="Test Section 1",
        zone_id="ZONE-A",
        area_hectares=150.0,
        canal_length_km=3.5,
        canal_type="lined",
        soil_type="clay",
        primary_crop="rice",
        crop_stage="vegetative",
        active=True
    )
    
    db_session.add(section)
    await db_session.commit()
    await db_session.refresh(section)
    
    return section

@pytest.fixture
async def sample_delivery(db_session, sample_section):
    """Create sample delivery for testing"""
    from src.models import WaterDelivery, DeliveryStatus
    from datetime import datetime, timedelta
    
    delivery = WaterDelivery(
        delivery_id="DEL-TEST-001",
        section_id=sample_section.id,
        gate_id="GATE-001",
        scheduled_start=datetime.now() - timedelta(hours=4),
        scheduled_end=datetime.now(),
        scheduled_volume_m3=5000,
        actual_start=datetime.now() - timedelta(hours=4),
        actual_end=datetime.now(),
        gate_outflow_m3=4800,
        section_inflow_m3=4600,
        transit_loss_m3=200,
        status=DeliveryStatus.COMPLETED,
        flow_readings=[
            {"timestamp": (datetime.now() - timedelta(hours=i)).isoformat(), 
             "flow_rate_m3s": 0.3 + i * 0.1}
            for i in range(5)
        ]
    )
    
    db_session.add(delivery)
    await db_session.commit()
    await db_session.refresh(delivery)
    
    return delivery

@pytest.fixture
def mock_external_services(monkeypatch):
    """Mock external service calls"""
    from unittest.mock import AsyncMock
    
    # Mock sensor data client
    async def mock_get_flow_readings(*args, **kwargs):
        return [
            {"timestamp": "2024-01-01T10:00:00", "flow_rate_m3s": 0.5, "gate_id": "GATE-001", "quality": 1.0},
            {"timestamp": "2024-01-01T11:00:00", "flow_rate_m3s": 0.6, "gate_id": "GATE-001", "quality": 1.0}
        ]
    
    # Mock GIS client
    async def mock_get_section_details(*args, **kwargs):
        return {
            "section_id": "SEC-001",
            "area_hectares": 100,
            "canal_length_km": 2.0,
            "canal_type": "lined",
            "soil_type": "clay",
            "location": {"lat": 13.7563, "lon": 100.5018}
        }
    
    # Mock weather client
    async def mock_get_environmental_conditions(*args, **kwargs):
        return {
            "temperature_c": 30,
            "humidity_percent": 65,
            "wind_speed_ms": 2.5,
            "solar_radiation_wm2": 250,
            "rainfall_mm": 0
        }
    
    # Mock SCADA client
    async def mock_get_gate_operational_data(*args, **kwargs):
        return {
            "gate_id": "GATE-001",
            "total_operations": 5,
            "avg_opening_percent": 85,
            "leakage_loss_m3": 10,
            "spillage_loss_m3": 5,
            "operational_efficiency": 0.95
        }
    
    # Apply mocks
    monkeypatch.setattr(
        "src.services.external_clients.SensorDataClient.get_flow_readings",
        AsyncMock(side_effect=mock_get_flow_readings)
    )
    monkeypatch.setattr(
        "src.services.external_clients.GISServiceClient.get_section_details",
        AsyncMock(side_effect=mock_get_section_details)
    )
    monkeypatch.setattr(
        "src.services.external_clients.WeatherServiceClient.get_environmental_conditions",
        AsyncMock(side_effect=mock_get_environmental_conditions)
    )
    monkeypatch.setattr(
        "src.services.external_clients.SCADAServiceClient.get_gate_operational_data",
        AsyncMock(side_effect=mock_get_gate_operational_data)
    )