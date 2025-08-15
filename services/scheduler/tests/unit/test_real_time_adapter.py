"""
Unit tests for Real-time Adaptation system.
"""

import pytest
import pytest_asyncio
from datetime import datetime, date, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.real_time_adapter import RealTimeAdapter
from src.schemas.adaptation import (
    GateFailureRequest,
    WeatherChangeRequest,
    DemandChangeRequest,
    FailureType,
    WeatherChangeType,
    DemandUrgency,
)


class TestRealTimeAdapter:
    """Test real-time adaptation functionality"""
    
    @pytest_asyncio.fixture
    async def adapter(self):
        """Create adapter instance with mocked dependencies"""
        mock_db = AsyncMock()
        mock_redis = AsyncMock()
        mock_ros = AsyncMock()
        mock_gis = AsyncMock()
        mock_flow = AsyncMock()
        
        adapter = RealTimeAdapter(
            db=mock_db,
            redis=mock_redis,
            ros_client=mock_ros,
            gis_client=mock_gis,
            flow_client=mock_flow,
        )
        
        return adapter
    
    @pytest_asyncio.fixture
    async def sample_schedule(self):
        """Sample schedule for testing"""
        schedule = MagicMock()
        schedule.id = uuid4()
        schedule.week_number = 15
        schedule.year = 2024
        schedule.status = "active"
        schedule.operations = []
        
        return schedule
    
    @pytest.mark.asyncio
    async def test_handle_gate_failure_reroute(self, adapter, sample_schedule):
        """Test handling gate failure with flow rerouting"""
        schedule_id = sample_schedule.id
        gate_id = "GATE-001"
        
        # Mock schedule retrieval
        adapter.db.execute = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = sample_schedule
        adapter.db.execute.return_value = result_mock
        
        # Mock alternative paths
        adapter.gis_client.find_alternative_paths = AsyncMock(return_value=[
            {
                "path_id": "ALT-001",
                "gates": ["GATE-002", "GATE-003"],
                "capacity": 8.0,
                "additional_distance_km": 2.5,
            }
        ])
        
        # Mock flow monitoring
        adapter.flow_client.get_gate_status = AsyncMock(return_value={
            "current_flow": 5.0,
            "downstream_demand": 5.0,
        })
        
        # Create failure request
        request = GateFailureRequest(
            schedule_id=schedule_id,
            gate_id=gate_id,
            failure_type=FailureType.MECHANICAL,
            failure_description="Motor failure",
            detected_at=datetime.utcnow(),
            estimated_repair_hours=4.0,
            can_partially_operate=False,
            affected_zones=["ZONE-001"],
        )
        
        # Execute
        response = await adapter.handle_gate_failure(
            schedule_id=str(schedule_id),
            gate_id=gate_id,
            failure_type=request.failure_type.value,
            estimated_repair_hours=request.estimated_repair_hours,
            timestamp=request.detected_at,
        )
        
        # Verify
        assert response["status"] == "completed"
        assert response["strategy"] == "reroute_flow"
        assert response["operations_modified"] > 0
        assert adapter.gis_client.find_alternative_paths.called
    
    @pytest.mark.asyncio
    async def test_handle_gate_failure_delay_operations(self, adapter, sample_schedule):
        """Test handling gate failure by delaying operations"""
        schedule_id = sample_schedule.id
        gate_id = "GATE-001"
        
        # Setup mocks
        adapter.db.execute = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = sample_schedule
        adapter.db.execute.return_value = result_mock
        
        # No alternative paths available
        adapter.gis_client.find_alternative_paths = AsyncMock(return_value=[])
        
        # Mock affected operations
        affected_ops = [
            MagicMock(
                id=uuid4(),
                gate_id=gate_id,
                operation_date=date.today() + timedelta(days=1),
                planned_start_time=datetime.now().time(),
                status="scheduled",
            )
            for _ in range(3)
        ]
        
        # Mock operation query
        ops_result = MagicMock()
        ops_result.scalars.return_value.all.return_value = affected_ops
        adapter.db.execute.return_value = ops_result
        
        # Create failure request
        request = GateFailureRequest(
            schedule_id=schedule_id,
            gate_id=gate_id,
            failure_type=FailureType.MECHANICAL,
            failure_description="Complete failure",
            detected_at=datetime.utcnow(),
            estimated_repair_hours=8.0,
            can_partially_operate=False,
            affected_zones=["ZONE-001"],
        )
        
        # Execute
        response = await adapter.handle_gate_failure(
            schedule_id=str(schedule_id),
            gate_id=gate_id,
            failure_type=request.failure_type.value,
            estimated_repair_hours=request.estimated_repair_hours,
            timestamp=request.detected_at,
        )
        
        # Verify
        assert response["status"] == "completed"
        assert response["strategy"] == "delay_operations"
        assert response["operations_rescheduled"] == len(affected_ops)
    
    @pytest.mark.asyncio
    async def test_handle_weather_change_rainfall(self, adapter, sample_schedule):
        """Test handling weather change with rainfall"""
        schedule_id = sample_schedule.id
        
        # Setup mocks
        adapter.db.execute = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = sample_schedule
        adapter.db.execute.return_value = result_mock
        
        # Mock ROS demand adjustment
        adapter.ros_client.calculate_demand_adjustment = AsyncMock(return_value={
            "zones": [
                {
                    "zone_id": "ZONE-001",
                    "original_demand_m3": 5000.0,
                    "adjusted_demand_m3": 4000.0,
                    "reduction_percent": 20.0,
                }
            ]
        })
        
        # Create weather change request
        weather_data = {
            "change_type": WeatherChangeType.RAINFALL.value,
            "rainfall_mm": 25.0,
            "affected_zones": ["ZONE-001"],
            "forecast_hours": 24,
            "expected_rainfall_mm": 40.0,
        }
        
        # Execute
        response = await adapter.handle_weather_change(
            schedule_id=str(schedule_id),
            weather_data=weather_data,
        )
        
        # Verify
        assert response["status"] == "completed"
        assert response["demand_adjusted"] is True
        assert response["total_adjustment_m3"] == -1000.0
        assert adapter.ros_client.calculate_demand_adjustment.called
    
    @pytest.mark.asyncio
    async def test_handle_demand_change_urgent(self, adapter, sample_schedule):
        """Test handling urgent demand change"""
        schedule_id = sample_schedule.id
        zone_id = "ZONE-001"
        
        # Setup mocks
        adapter.db.execute = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = sample_schedule
        adapter.db.execute.return_value = result_mock
        
        # Mock optimizer
        with patch('src.services.real_time_adapter.ScheduleOptimizer') as mock_optimizer_class:
            mock_optimizer = AsyncMock()
            mock_optimizer_class.return_value = mock_optimizer
            
            mock_optimizer.generate_emergency_operations = AsyncMock(return_value=[
                {
                    "gate_id": "GATE-001",
                    "operation_date": date.today(),
                    "team_id": "TEAM-001",
                    "flow_rate": 5.0,
                    "duration_hours": 2.0,
                }
            ])
            
            # Execute
            response = await adapter.handle_demand_change(
                schedule_id=str(schedule_id),
                zone_id=zone_id,
                plot_ids=["PLOT-001", "PLOT-002"],
                demand_change_m3=1000.0,
                urgency=DemandUrgency.CRITICAL.value,
                reason="Crop stress detected",
            )
            
            # Verify
            assert response["status"] == "completed"
            assert response["operations_added"] > 0
            assert response["urgency_handled"] is True
            mock_optimizer.generate_emergency_operations.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reoptimize_schedule(self, adapter, sample_schedule):
        """Test full schedule reoptimization"""
        schedule_id = sample_schedule.id
        
        # Setup mocks
        adapter.db.execute = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = sample_schedule
        adapter.db.execute.return_value = result_mock
        
        # Mock optimizer
        with patch('src.services.real_time_adapter.ScheduleOptimizer') as mock_optimizer_class:
            mock_optimizer = AsyncMock()
            mock_optimizer_class.return_value = mock_optimizer
            
            # Mock reoptimization result
            new_schedule = MagicMock()
            new_schedule.id = uuid4()
            new_schedule.version = 2
            mock_optimizer.reoptimize_from_date = AsyncMock(return_value=new_schedule)
            
            # Execute
            response = await adapter.reoptimize_schedule(
                schedule_id=str(schedule_id),
                from_date=date.today() + timedelta(days=1),
                constraints={
                    "preserve_completed": True,
                    "minimize_changes": True,
                },
                reason="Multiple gate failures",
            )
            
            # Verify
            assert response["status"] == "completed"
            assert response["new_version"] == 2
            assert "reoptimization_complete" in response
            mock_optimizer.reoptimize_from_date.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_publish_adaptation_event(self, adapter):
        """Test publishing adaptation events to Redis"""
        event_data = {
            "type": "gate_failure",
            "gate_id": "GATE-001",
            "timestamp": datetime.utcnow().isoformat(),
            "action": "reroute_flow",
        }
        
        # Execute
        await adapter._publish_adaptation_event(
            schedule_id=str(uuid4()),
            event_type="gate_failure",
            event_data=event_data,
        )
        
        # Verify Redis publish was called
        adapter.redis.publish.assert_called_once()
        call_args = adapter.redis.publish.call_args
        assert "adaptation:" in call_args[0][0]  # Channel name
        assert call_args[0][1]["event_type"] == "gate_failure"
    
    @pytest.mark.asyncio
    async def test_calculate_impact_assessment(self, adapter):
        """Test impact assessment calculation"""
        # Mock flow monitoring data
        adapter.flow_client.get_downstream_impacts = AsyncMock(return_value={
            "affected_gates": ["GATE-002", "GATE-003"],
            "total_flow_reduction": 5.0,
            "affected_zones": ["ZONE-001", "ZONE-002"],
        })
        
        # Execute
        impact = await adapter._calculate_impact_assessment(
            gate_id="GATE-001",
            failure_type="complete",
        )
        
        # Verify
        assert len(impact["affected_gates"]) == 2
        assert impact["total_flow_reduction"] == 5.0
        assert len(impact["affected_zones"]) == 2
    
    @pytest.mark.asyncio 
    async def test_validate_adaptation_constraints(self, adapter):
        """Test validation of adaptation constraints"""
        constraints = {
            "max_delay_hours": 24,
            "min_delivery_percent": 80,
            "preserve_priority_zones": True,
            "priority_zones": ["ZONE-001"],
        }
        
        proposed_changes = {
            "operations_delayed": 5,
            "max_delay_hours": 20,
            "delivery_satisfaction": 85,
            "affected_zones": ["ZONE-002"],
        }
        
        # Should pass validation
        is_valid = await adapter._validate_adaptation_constraints(
            constraints, proposed_changes
        )
        assert is_valid is True
        
        # Should fail - too much delay
        proposed_changes["max_delay_hours"] = 30
        is_valid = await adapter._validate_adaptation_constraints(
            constraints, proposed_changes
        )
        assert is_valid is False
        
        # Should fail - affects priority zone
        proposed_changes["max_delay_hours"] = 20
        proposed_changes["affected_zones"] = ["ZONE-001"]
        is_valid = await adapter._validate_adaptation_constraints(
            constraints, proposed_changes
        )
        assert is_valid is False