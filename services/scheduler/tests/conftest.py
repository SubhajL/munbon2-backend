"""
Pytest configuration and fixtures for scheduler service tests.
"""

import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator, Dict, Any
from datetime import datetime, date, time, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.main import app
from src.core.database import Base, get_db
from src.core.redis import get_redis_client
from src.core.config import settings
from src.models.schedule import WeeklySchedule, ScheduledOperation
from src.models.team import FieldTeam


# Test database setup
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_engine():
    """Create async test database engine"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest_asyncio.fixture
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for tests"""
    async_session_maker = sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_maker() as session:
        yield session


@pytest.fixture
def test_client(async_session) -> TestClient:
    """Create test client with dependency overrides"""
    
    async def override_get_db():
        yield async_session
    
    async def override_get_redis():
        # Mock Redis client for tests
        return MockRedisClient()
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis
    
    with TestClient(app) as client:
        yield client
    
    app.dependency_overrides.clear()


class MockRedisClient:
    """Mock Redis client for testing"""
    
    def __init__(self):
        self.data = {}
        self.pubsub_messages = []
    
    async def set(self, key: str, value: str, ex: int = None):
        self.data[key] = value
    
    async def get(self, key: str) -> str:
        return self.data.get(key)
    
    async def delete(self, key: str):
        self.data.pop(key, None)
    
    async def set_json(self, key: str, value: Dict[str, Any]):
        self.data[key] = value
    
    async def get_json(self, key: str) -> Dict[str, Any]:
        return self.data.get(key)
    
    async def publish(self, channel: str, message: Dict[str, Any]):
        self.pubsub_messages.append({"channel": channel, "message": message})
    
    async def exists(self, key: str) -> bool:
        return key in self.data


@pytest.fixture
def sample_schedule_data() -> Dict[str, Any]:
    """Sample schedule data for testing"""
    return {
        "week_number": 15,
        "year": 2024,
        "constraints": {
            "max_daily_operations": 50,
            "min_flow_rate": 0.5,
            "team_overtime_allowed": False,
            "priority_zones": ["ZONE-001", "ZONE-002"],
        }
    }


@pytest.fixture
def sample_team_data() -> Dict[str, Any]:
    """Sample team data for testing"""
    return {
        "team_code": "TEAM-001",
        "name": "Field Team Alpha",
        "base_location": "Central Station",
        "base_latitude": 13.7563,
        "base_longitude": 100.5018,
        "primary_phone": "+66812345678",
        "capabilities": ["gate_operation", "inspection"],
        "vehicle_type": "pickup",
        "average_speed_kmh": 40,
        "members": [
            {
                "id": "M001",
                "name": "John Doe",
                "role": "Team Leader",
                "phone": "+66812345678",
                "capabilities": ["gate_operation", "inspection"],
            },
            {
                "id": "M002", 
                "name": "Jane Smith",
                "role": "Operator",
                "phone": "+66823456789",
                "capabilities": ["gate_operation"],
            }
        ]
    }


@pytest.fixture
def sample_operation_data() -> Dict[str, Any]:
    """Sample operation data for testing"""
    return {
        "gate_id": "GATE-001",
        "gate_name": "Main Canal Gate 1",
        "team_id": "TEAM-001",
        "team_name": "Field Team Alpha",
        "operation_type": "adjust",
        "operation_date": date.today() + timedelta(days=1),
        "planned_start_time": time(8, 0),
        "planned_end_time": time(8, 30),
        "duration_minutes": 30,
        "operation_sequence": 1,
        "target_opening_percent": 75.0,
        "target_flow_rate": 5.5,
        "latitude": 13.7563,
        "longitude": 100.5018,
        "location_description": "Main canal intersection",
    }


@pytest.fixture
def sample_gate_failure_data() -> Dict[str, Any]:
    """Sample gate failure adaptation request"""
    return {
        "schedule_id": str(uuid4()),
        "gate_id": "GATE-001",
        "failure_type": "mechanical",
        "failure_description": "Gate motor malfunction",
        "detected_at": datetime.utcnow().isoformat(),
        "estimated_repair_hours": 4.0,
        "can_partially_operate": True,
        "partial_capacity_percent": 50.0,
        "affected_zones": ["ZONE-001"],
    }


@pytest.fixture
def sample_weather_change_data() -> Dict[str, Any]:
    """Sample weather change adaptation request"""
    return {
        "schedule_id": str(uuid4()),
        "change_type": "rainfall",
        "detected_at": datetime.utcnow().isoformat(),
        "rainfall_mm": 25.5,
        "forecast_hours": 24,
        "expected_rainfall_mm": 40.0,
        "affected_zones": ["ZONE-001", "ZONE-002"],
        "recommended_adjustment_percent": -20.0,
    }


@pytest_asyncio.fixture
async def sample_schedule(async_session: AsyncSession) -> WeeklySchedule:
    """Create sample schedule in database"""
    schedule = WeeklySchedule(
        schedule_code="SCH-2024-W15",
        week_number=15,
        year=2024,
        status="draft",
        version=1,
        total_water_demand_m3=50000.0,
        field_days=2,
        start_date=date(2024, 4, 8),
        end_date=date(2024, 4, 14),
        created_by="test_user",
    )
    
    async_session.add(schedule)
    await async_session.commit()
    await async_session.refresh(schedule)
    
    return schedule


@pytest_asyncio.fixture
async def sample_team(async_session: AsyncSession) -> FieldTeam:
    """Create sample team in database"""
    team = FieldTeam(
        team_code="TEAM-001",
        name="Field Team Alpha",
        base_location="Central Station",
        base_latitude=13.7563,
        base_longitude=100.5018,
        primary_phone="+66812345678",
        capabilities=["gate_operation", "inspection"],
        vehicle_type="pickup",
        average_speed_kmh=40,
        status="available",
        active=True,
    )
    
    async_session.add(team)
    await async_session.commit()
    await async_session.refresh(team)
    
    return team


@pytest.fixture
def mock_external_services(monkeypatch):
    """Mock external service calls"""
    
    class MockROSClient:
        async def get_weekly_demands(self, week_number: int, year: int):
            return {
                "zones": [
                    {
                        "zone_id": "ZONE-001",
                        "total_demand_m3": 25000.0,
                        "plots": [
                            {
                                "plot_id": "PLOT-001",
                                "demand_m3": 5000.0,
                                "crop_type": "rice",
                                "growth_stage": "vegetative",
                            }
                        ]
                    }
                ]
            }
    
    class MockGISClient:
        async def get_hydraulic_network(self, zone_ids: list):
            return {
                "gates": [
                    {
                        "gate_id": "GATE-001",
                        "type": "main",
                        "latitude": 13.7563,
                        "longitude": 100.5018,
                        "max_flow": 10.0,
                    }
                ],
                "canals": [
                    {
                        "canal_id": "CANAL-001",
                        "capacity_m3s": 15.0,
                        "length_km": 5.2,
                    }
                ]
            }
        
        async def calculate_travel_distance(self, from_coords: tuple, to_coords: tuple):
            # Simple distance calculation for testing
            return 5.0
    
    class MockFlowMonitoringClient:
        async def get_current_gate_status(self, gate_id: str):
            return {
                "gate_id": gate_id,
                "current_opening": 50.0,
                "current_flow": 3.5,
                "last_update": datetime.utcnow().isoformat(),
            }
    
    monkeypatch.setattr("src.services.clients.ROSClient", MockROSClient)
    monkeypatch.setattr("src.services.clients.GISClient", MockGISClient)
    monkeypatch.setattr("src.services.clients.FlowMonitoringClient", MockFlowMonitoringClient)


@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """Mock authentication headers"""
    return {
        "Authorization": "Bearer test-token-123",
        "X-User-ID": "test-user",
    }