"""
Pytest configuration and fixtures for Flow Monitoring Service tests
"""

import pytest
import asyncio
from typing import Dict, Any
from datetime import datetime
import json
from unittest.mock import Mock, AsyncMock

# Add src to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.gate_registry import GateRegistry, ControlMode, AutomatedGate, ManualGate
from core.calibrated_gate_hydraulics import CalibratedGateHydraulics, GateProperties, GateCalibration
from core.enhanced_hydraulic_solver import EnhancedHydraulicSolver, NetworkNode, NetworkNodeType
from db.connections import DatabaseManager


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_network_config():
    """Mock network configuration for testing"""
    return {
        "nodes": {
            "Reservoir": {
                "type": "reservoir",
                "elevation_m": 100.0,
                "min_depth_m": 2.0,
                "max_depth_m": 10.0
            },
            "Junction_1": {
                "type": "junction",
                "elevation_m": 95.0,
                "min_depth_m": 0.5,
                "max_depth_m": 5.0
            },
            "Zone_1": {
                "type": "delivery",
                "elevation_m": 90.0,
                "demand_m3s": 2.5,
                "min_depth_m": 0.3,
                "max_depth_m": 3.0
            },
            "Zone_2": {
                "type": "delivery",
                "elevation_m": 88.0,
                "demand_m3s": 3.0,
                "min_depth_m": 0.3,
                "max_depth_m": 3.0
            }
        },
        "gates": {
            "G_RES_J1": {
                "upstream": "Reservoir",
                "downstream": "Junction_1",
                "type": "radial",
                "width_m": 5.0,
                "height_m": 4.0,
                "sill_elevation_m": 95.0
            },
            "G_J1_Z1": {
                "upstream": "Junction_1",
                "downstream": "Zone_1",
                "type": "slide",
                "width_m": 3.0,
                "height_m": 2.5,
                "sill_elevation_m": 90.0
            }
        },
        "canals": {
            "C_RES_J1": {
                "upstream": "Reservoir",
                "downstream": "Junction_1",
                "length_m": 1000.0,
                "bottom_width_m": 10.0,
                "side_slope": 1.5,
                "manning_n": 0.025,
                "bed_slope": 0.0001
            }
        }
    }


@pytest.fixture
def gate_registry():
    """Create a test gate registry"""
    registry = GateRegistry()
    
    # Add automated gates
    registry.automated_gates["G_RES_J1"] = AutomatedGate(
        gate_id="G_RES_J1",
        location="Reservoir to Junction 1",
        control_mode=ControlMode.AUTO,
        scada_tag="SCADA.G_RES_J1",
        control_equipment=Mock(),
        equipment_status=Mock(),
        last_communication=datetime.now()
    )
    
    # Add manual gates
    registry.manual_gates["G_J1_Z1"] = ManualGate(
        gate_id="G_J1_Z1",
        location="Junction 1 to Zone 1",
        control_mode=ControlMode.MANUAL,
        operation_details=Mock(),
        field_team_zone="Team_A"
    )
    
    return registry


@pytest.fixture
def calibrated_hydraulics():
    """Create calibrated gate hydraulics instance"""
    gate_properties = {
        "G_RES_J1": GateProperties(
            gate_id="G_RES_J1",
            gate_type="radial",
            width_m=5.0,
            height_m=4.0,
            sill_elevation_m=95.0,
            discharge_coefficient=0.65
        ),
        "G_J1_Z1": GateProperties(
            gate_id="G_J1_Z1",
            gate_type="slide",
            width_m=3.0,
            height_m=2.5,
            sill_elevation_m=90.0,
            discharge_coefficient=0.60
        )
    }
    
    calibrations = {
        "G_RES_J1": GateCalibration(
            gate_id="G_RES_J1",
            K1=0.72,
            K2=-0.15,
            min_opening_m=0.1,
            max_tested_opening_m=3.5,
            calibration_date="2024-06-15",
            r_squared=0.98
        )
    }
    
    return CalibratedGateHydraulics(gate_properties, calibrations)


@pytest.fixture
async def mock_db_manager():
    """Mock database manager"""
    db_manager = Mock(spec=DatabaseManager)
    db_manager.connect_all = AsyncMock()
    db_manager.disconnect_all = AsyncMock()
    db_manager.check_health = AsyncMock(return_value={
        "postgres": True,
        "influxdb": True,
        "timescale": True,
        "redis": True
    })
    db_manager.postgres_pool = Mock()
    db_manager.influx_client = Mock()
    db_manager.timescale_pool = Mock()
    db_manager.redis_client = Mock()
    
    return db_manager


@pytest.fixture
def sample_gate_states():
    """Sample gate states for testing"""
    return {
        "G_RES_J1": {
            "opening_m": 2.0,
            "flow_m3s": 15.5,
            "upstream_level_m": 105.0,
            "downstream_level_m": 98.0
        },
        "G_J1_Z1": {
            "opening_m": 1.5,
            "flow_m3s": 8.2,
            "upstream_level_m": 98.0,
            "downstream_level_m": 93.0
        }
    }


@pytest.fixture
def sample_schedule():
    """Sample irrigation schedule for testing"""
    return {
        "deliveries": [
            {
                "node_id": "Zone_1",
                "flow_rate": 2.5,
                "duration_hours": 4,
                "start_time": "08:00"
            },
            {
                "node_id": "Zone_2", 
                "flow_rate": 3.0,
                "duration_hours": 6,
                "start_time": "08:00"
            }
        ],
        "date": "2024-08-13"
    }


@pytest.fixture
async def test_client(mock_db_manager):
    """Create test client for API testing"""
    from fastapi.testclient import TestClient
    from main import app
    
    # Override dependencies
    from api import gates
    gates.gate_controller = Mock()
    
    client = TestClient(app)
    return client