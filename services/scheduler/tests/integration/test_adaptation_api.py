"""
Integration tests for adaptation API endpoints.
"""

import pytest
from datetime import datetime
from uuid import uuid4

from fastapi import status


class TestAdaptationAPI:
    """Test adaptation API endpoints"""
    
    @pytest.mark.asyncio
    async def test_handle_gate_failure(
        self, test_client, sample_schedule, sample_gate_failure_data, 
        mock_external_services, auth_headers
    ):
        """Test handling gate failure adaptation"""
        # Set schedule as active
        sample_schedule.status = "active"
        sample_gate_failure_data["schedule_id"] = str(sample_schedule.id)
        
        response = test_client.post(
            "/api/v1/adaptation/gate-failure",
            json=sample_gate_failure_data,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["request_type"] == "gate_failure"
        assert data["status"] == "completed"
        assert "selected_strategy" in data
        assert data["selected_strategy"] in [
            "reroute_flow", "delay_operations", "partial_delivery"
        ]
        assert data["gate_id"] == sample_gate_failure_data["gate_id"]
    
    @pytest.mark.asyncio
    async def test_handle_weather_change(
        self, test_client, sample_schedule, sample_weather_change_data,
        mock_external_services, auth_headers
    ):
        """Test handling weather change adaptation"""
        sample_schedule.status = "active"
        sample_weather_change_data["schedule_id"] = str(sample_schedule.id)
        
        response = test_client.post(
            "/api/v1/adaptation/weather-change",
            json=sample_weather_change_data,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["request_type"] == "weather_change"
        assert data["status"] == "completed"
        assert "demand_adjustment_m3" in data
        assert data["affected_zones"] == sample_weather_change_data["affected_zones"]
    
    @pytest.mark.asyncio
    async def test_handle_demand_change(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test handling demand change request"""
        sample_schedule.status = "active"
        
        demand_change_data = {
            "schedule_id": str(sample_schedule.id),
            "zone_id": "ZONE-001",
            "plot_ids": ["PLOT-001", "PLOT-002"],
            "change_type": "increase",
            "urgency": "high",
            "original_demand_m3": 1000.0,
            "new_demand_m3": 1500.0,
            "effective_from": datetime.utcnow().isoformat(),
            "reason": "High temperature stress",
            "requestor": "Field Officer",
        }
        
        response = test_client.post(
            "/api/v1/adaptation/demand-change",
            json=demand_change_data,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["request_type"] == "demand_change"
        assert data["zone_id"] == demand_change_data["zone_id"]
        assert "operations_added" in data or "operations_modified" in data
    
    @pytest.mark.asyncio
    async def test_handle_team_unavailable(
        self, test_client, sample_schedule, sample_team, auth_headers
    ):
        """Test handling team unavailability"""
        sample_schedule.status = "active"
        
        unavailable_data = {
            "schedule_id": str(sample_schedule.id),
            "team_id": str(sample_team.id),
            "unavailable_from": datetime.utcnow().isoformat(),
            "reason": "Vehicle breakdown",
            "affected_operation_ids": [str(uuid4()) for _ in range(3)],
            "can_delay_operations": True,
            "max_delay_hours": 4.0,
        }
        
        response = test_client.post(
            "/api/v1/adaptation/team-unavailable",
            json=unavailable_data,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["request_type"] == "team_unavailable"
        assert data["team_id"] == unavailable_data["team_id"]
        assert "operations_reassigned" in data or "operations_rescheduled" in data
    
    @pytest.mark.asyncio
    async def test_reoptimize_schedule(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test triggering schedule reoptimization"""
        sample_schedule.status = "active"
        
        reoptimize_data = {
            "schedule_id": str(sample_schedule.id),
            "from_date": datetime.utcnow().date().isoformat(),
            "trigger_type": "system_optimization",
            "trigger_description": "Multiple constraints violated",
            "optimization_objectives": [
                "minimize_changes",
                "satisfy_demands",
                "minimize_travel"
            ],
            "allow_partial_delivery": True,
            "preserve_completed_operations": True,
        }
        
        response = test_client.post(
            "/api/v1/adaptation/reoptimize",
            json=reoptimize_data,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["status"] == "completed"
        assert "new_schedule_id" in data
        assert "optimization_time_seconds" in data
    
    @pytest.mark.asyncio
    async def test_get_adaptation_history(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test retrieving adaptation history for a schedule"""
        response = test_client.get(
            f"/api/v1/adaptation/history/{sample_schedule.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "total_adaptations" in data
        assert "adaptations_by_type" in data
        assert "recent_adaptations" in data
        assert isinstance(data["recent_adaptations"], list)
    
    @pytest.mark.asyncio
    async def test_emergency_override(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test emergency override functionality"""
        sample_schedule.status = "active"
        
        emergency_data = {
            "schedule_id": str(sample_schedule.id),
            "override_type": "flood_emergency",
            "affected_zones": ["ZONE-001", "ZONE-002"],
            "action": "close_all_gates",
            "authorization_code": "EMRG-12345",
            "effective_immediately": True,
        }
        
        response = test_client.post(
            "/api/v1/adaptation/emergency-override",
            json=emergency_data,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["override_applied"] is True
        assert data["gates_affected"] > 0
        assert "emergency_id" in data
    
    @pytest.mark.asyncio
    async def test_adaptation_validation(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test adaptation request validation"""
        # Invalid failure type
        invalid_data = {
            "schedule_id": str(sample_schedule.id),
            "gate_id": "GATE-001",
            "failure_type": "invalid_type",  # Invalid
            "failure_description": "Test",
            "detected_at": datetime.utcnow().isoformat(),
            "estimated_repair_hours": 4.0,
        }
        
        response = test_client.post(
            "/api/v1/adaptation/gate-failure",
            json=invalid_data,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Missing required fields
        incomplete_data = {
            "schedule_id": str(sample_schedule.id),
            "gate_id": "GATE-001",
            # Missing failure_type and other required fields
        }
        
        response = test_client.post(
            "/api/v1/adaptation/gate-failure",
            json=incomplete_data,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    @pytest.mark.asyncio
    async def test_adaptation_for_inactive_schedule(
        self, test_client, sample_schedule, sample_gate_failure_data, auth_headers
    ):
        """Test adaptation fails for inactive schedule"""
        sample_schedule.status = "draft"  # Not active
        sample_gate_failure_data["schedule_id"] = str(sample_schedule.id)
        
        response = test_client.post(
            "/api/v1/adaptation/gate-failure",
            json=sample_gate_failure_data,
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not active" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_concurrent_adaptations(
        self, test_client, sample_schedule, auth_headers
    ):
        """Test handling concurrent adaptation requests"""
        sample_schedule.status = "active"
        
        # Create multiple adaptation requests
        requests = []
        
        # Gate failure
        requests.append(test_client.post(
            "/api/v1/adaptation/gate-failure",
            json={
                "schedule_id": str(sample_schedule.id),
                "gate_id": "GATE-001",
                "failure_type": "mechanical",
                "failure_description": "Test 1",
                "detected_at": datetime.utcnow().isoformat(),
                "estimated_repair_hours": 2.0,
            },
            headers=auth_headers,
        ))
        
        # Weather change
        requests.append(test_client.post(
            "/api/v1/adaptation/weather-change",
            json={
                "schedule_id": str(sample_schedule.id),
                "change_type": "rainfall",
                "detected_at": datetime.utcnow().isoformat(),
                "rainfall_mm": 15.0,
                "affected_zones": ["ZONE-001"],
            },
            headers=auth_headers,
        ))
        
        # All requests should be handled
        for req in requests:
            assert req.status_code in [
                status.HTTP_200_OK,
                status.HTTP_202_ACCEPTED
            ]
    
    @pytest.mark.asyncio
    async def test_get_contingency_plans(
        self, test_client, auth_headers
    ):
        """Test retrieving available contingency plans"""
        response = test_client.get(
            "/api/v1/adaptation/contingency-plans",
            headers=auth_headers,
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        # Check structure if plans exist
        if data:
            plan = data[0]
            assert "plan_id" in plan
            assert "name" in plan
            assert "trigger_conditions" in plan
            assert "automatic_actions" in plan