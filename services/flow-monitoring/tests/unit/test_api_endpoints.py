"""
Unit tests for API endpoints
Tests all REST API endpoints for the flow monitoring service
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import json

from main import app
from core.gate_registry import ControlMode, EquipmentStatus
from api import gates as gates_api


class TestAPIEndpoints:
    """Test suite for API endpoints"""
    
    @pytest.fixture
    def client(self, mock_db_manager):
        """Create test client"""
        # Mock dependencies
        with patch('main.db_manager', mock_db_manager):
            with patch('main.kafka_consumer', Mock()):
                with patch('api.gates.gate_controller', Mock()):
                    client = TestClient(app)
                    yield client
    
    @pytest.fixture
    def mock_gate_controller(self):
        """Mock gate controller for API tests"""
        controller = Mock()
        controller.gate_registry = Mock()
        controller.hydraulic_solver = Mock()
        controller.get_all_gate_states = Mock()
        controller.get_gate_state = Mock()
        controller.update_manual_gate = Mock()
        controller.get_manual_instructions = Mock()
        controller.request_mode_transition = Mock()
        controller.get_synchronization_status = Mock()
        return controller
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "unhealthy"]
        assert "databases" in data
        assert data["service"] == "flow-monitoring"
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "flow-monitoring"
        assert "Flow Monitoring Service" in data["description"]
    
    def test_get_all_gates_state(self, client, mock_gate_controller):
        """Test GET /api/v1/gates/state endpoint"""
        # Mock gate states
        mock_states = {
            "gates": {
                "G_RES_J1": {
                    "type": "automated",
                    "mode": "auto",
                    "opening_m": 2.0,
                    "opening_percentage": 50.0,
                    "flow_m3s": 15.5,
                    "upstream_level_m": 105.0,
                    "downstream_level_m": 98.0,
                    "last_update": datetime.now().isoformat()
                },
                "G_J1_Z1": {
                    "type": "manual",
                    "mode": "manual",
                    "opening_m": 1.5,
                    "opening_percentage": 60.0,
                    "flow_m3s": 8.2,
                    "upstream_level_m": 98.0,
                    "downstream_level_m": 93.0,
                    "last_update": datetime.now().isoformat()
                }
            },
            "timestamp": datetime.now().isoformat()
        }
        
        with patch('api.gates.gate_controller', mock_gate_controller):
            mock_gate_controller.get_all_gate_states.return_value = mock_states
            
            response = client.get("/api/v1/gates/state")
            
            assert response.status_code == 200
            data = response.json()
            assert "gates" in data
            assert len(data["gates"]) == 2
            assert "G_RES_J1" in data["gates"]
    
    def test_get_single_gate_state(self, client, mock_gate_controller):
        """Test GET /api/v1/gates/state/{gate_id} endpoint"""
        gate_id = "G_RES_J1"
        mock_state = {
            "gate_id": gate_id,
            "type": "automated",
            "mode": "auto",
            "opening_m": 2.0,
            "flow_m3s": 15.5
        }
        
        with patch('api.gates.gate_controller', mock_gate_controller):
            mock_gate_controller.get_gate_state.return_value = mock_state
            
            response = client.get(f"/api/v1/gates/state/{gate_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["gate_id"] == gate_id
            assert data["opening_m"] == 2.0
    
    def test_update_manual_gate_state(self, client, mock_gate_controller):
        """Test PUT /api/v1/gates/manual/{gate_id}/state endpoint"""
        gate_id = "G_J1_Z1"
        update_data = {
            "opening_percentage": 75.0,
            "operator_id": "OP-123",
            "notes": "Increased flow for irrigation"
        }
        
        with patch('api.gates.gate_controller', mock_gate_controller):
            mock_gate_controller.update_manual_gate.return_value = {
                "success": True,
                "gate_id": gate_id,
                "new_opening_percentage": 75.0,
                "timestamp": datetime.now().isoformat()
            }
            
            response = client.put(
                f"/api/v1/gates/manual/{gate_id}/state",
                json=update_data
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["new_opening_percentage"] == 75.0
    
    def test_verify_schedule(self, client, mock_gate_controller):
        """Test POST /api/v1/hydraulics/verify-schedule endpoint"""
        schedule = {
            "deliveries": [
                {
                    "node_id": "Zone_1",
                    "flow_rate": 2.5,
                    "duration_hours": 4
                },
                {
                    "node_id": "Zone_2",
                    "flow_rate": 3.0,
                    "duration_hours": 6
                }
            ]
        }
        
        mock_verification = {
            "is_feasible": True,
            "total_demand": 5.5,
            "system_capacity": 20.0,
            "system_utilization": 0.275,
            "required_gates": {
                "G_RES_J1": 2.5,
                "G_J1_Z1": 1.8
            },
            "warnings": []
        }
        
        with patch('api.hydraulics.verify_irrigation_schedule') as mock_verify:
            mock_verify.return_value = mock_verification
            
            response = client.post(
                "/api/v1/hydraulics/verify-schedule",
                json=schedule
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["is_feasible"] is True
            assert data["data"]["total_demand"] == 5.5
    
    def test_mode_transition_request(self, client, mock_gate_controller):
        """Test POST /api/v1/gates/mode/transition endpoint"""
        transition_request = {
            "gate_id": "G_RES_J1",
            "target_mode": "manual",
            "reason": "SCADA maintenance required",
            "force": False
        }
        
        with patch('api.gates.gate_controller', mock_gate_controller):
            mock_gate_controller.request_mode_transition.return_value = {
                "success": True,
                "gate_id": "G_RES_J1",
                "from_mode": "auto",
                "to_mode": "manual",
                "estimated_completion": (datetime.now() + timedelta(minutes=5)).isoformat()
            }
            
            response = client.post(
                "/api/v1/gates/mode/transition",
                json=transition_request
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["to_mode"] == "manual"
    
    def test_get_manual_instructions(self, client, mock_gate_controller):
        """Test GET /api/v1/gates/manual/instructions endpoint"""
        mock_instructions = {
            "generated_at": datetime.now().isoformat(),
            "instructions": [
                {
                    "gate_id": "G_J1_Z1",
                    "location": "Junction 1 to Zone 1",
                    "current_opening": 1.5,
                    "target_opening": 2.0,
                    "priority": "high",
                    "team": "Team_A",
                    "estimated_time_min": 30
                }
            ],
            "coordination_notes": [
                "Coordinate with automated gate G_RES_J1"
            ]
        }
        
        with patch('api.gates.gate_controller', mock_gate_controller):
            mock_gate_controller.get_manual_instructions.return_value = mock_instructions
            
            response = client.get("/api/v1/gates/manual/instructions")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["instructions"]) == 1
            assert data["instructions"][0]["gate_id"] == "G_J1_Z1"
    
    def test_synchronization_status(self, client, mock_gate_controller):
        """Test GET /api/v1/gates/synchronization/status endpoint"""
        mock_sync_status = {
            "overall_sync_quality": 0.95,
            "last_sync": datetime.now().isoformat(),
            "gates": {
                "G_RES_J1": {
                    "sync_status": "good",
                    "deviation_m": 0.02,
                    "last_update": datetime.now().isoformat()
                },
                "G_J1_Z1": {
                    "sync_status": "pending",
                    "deviation_m": None,
                    "last_update": (datetime.now() - timedelta(hours=2)).isoformat()
                }
            }
        }
        
        with patch('api.gates.gate_controller', mock_gate_controller):
            mock_gate_controller.get_synchronization_status.return_value = mock_sync_status
            
            response = client.get("/api/v1/gates/synchronization/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data["overall_sync_quality"] == 0.95
            assert "G_RES_J1" in data["gates"]
    
    def test_error_handling_gate_not_found(self, client, mock_gate_controller):
        """Test 404 error for non-existent gate"""
        with patch('api.gates.gate_controller', mock_gate_controller):
            mock_gate_controller.get_gate_state.return_value = None
            
            response = client.get("/api/v1/gates/state/UNKNOWN_GATE")
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
    
    def test_error_handling_invalid_mode(self, client, mock_gate_controller):
        """Test 400 error for invalid mode transition"""
        transition_request = {
            "gate_id": "G_J1_Z1",
            "target_mode": "invalid_mode",
            "reason": "Test"
        }
        
        response = client.post(
            "/api/v1/gates/mode/transition",
            json=transition_request
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_metrics_endpoint(self, client):
        """Test Prometheus metrics endpoint"""
        response = client.get("/metrics")
        
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        # Should contain Prometheus metrics
        assert "# HELP" in response.text
        assert "# TYPE" in response.text