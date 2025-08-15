"""
Integration tests for mode transition scenarios
Tests complete workflows for transitioning between operational modes
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from core.gate_registry import GateRegistry, ControlMode, EquipmentStatus
from core.enhanced_hydraulic_solver import EnhancedHydraulicSolver
from core.state_preservation import StatePreservationSystem, TransitionType
from core.gradual_transition_controller import GradualTransitionController, TransitionStrategy
from controllers.dual_mode_gate_controller import DualModeGateController


class TestModeTransitionIntegration:
    """Integration tests for mode transition scenarios"""
    
    @pytest.fixture
    async def integrated_system(self, mock_network_config, mock_db_manager):
        """Create integrated system with all components"""
        # Create components
        gate_registry = GateRegistry()
        hydraulic_solver = EnhancedHydraulicSolver(mock_network_config, gate_registry)
        state_preservation = StatePreservationSystem(mock_db_manager, None)
        transition_controller = GradualTransitionController(hydraulic_solver, gate_registry)
        
        # Create main controller
        controller = DualModeGateController(
            mock_db_manager,
            "mock_network.json",
            "mock_geometry.json"
        )
        controller.gate_registry = gate_registry
        controller.hydraulic_solver = hydraulic_solver
        controller.state_preservation = state_preservation
        controller.transition_controller = transition_controller
        
        return controller
    
    @pytest.mark.asyncio
    async def test_auto_to_manual_transition_on_scada_failure(self, integrated_system):
        """Test automatic transition from AUTO to MANUAL on SCADA failure"""
        controller = integrated_system
        gate_id = "G_RES_J1"
        
        # Add automated gate
        controller.gate_registry.add_automated_gate(Mock(
            gate_id=gate_id,
            location="Test Gate",
            control_mode=ControlMode.AUTO,
            scada_tag="SCADA.TEST",
            control_equipment=Mock(),
            equipment_status=EquipmentStatus.OPERATIONAL
        ))
        
        # Simulate SCADA communication failures
        for _ in range(3):
            controller.gate_registry.record_communication(gate_id, success=False)
            await asyncio.sleep(0.1)
        
        # Check for automatic transitions
        transitions = controller.gate_registry.check_transition_rules()
        
        assert len(transitions) > 0
        assert any(t["gate_id"] == gate_id and t["to_mode"] == ControlMode.MANUAL 
                  for t in transitions)
        
        # Execute transition
        for transition in transitions:
            if transition["gate_id"] == gate_id:
                success = await controller.execute_mode_transition(
                    transition["gate_id"],
                    transition["to_mode"],
                    transition["reason"]
                )
                assert success is True
        
        # Verify mode changed
        assert controller.gate_registry.get_gate_mode(gate_id) == ControlMode.MANUAL
    
    @pytest.mark.asyncio
    async def test_manual_to_auto_transition_with_validation(self, integrated_system):
        """Test transitioning from MANUAL to AUTO with safety validation"""
        controller = integrated_system
        gate_id = "G_J1_Z1"
        
        # Start in manual mode
        controller.gate_registry.update_gate_mode(gate_id, ControlMode.MANUAL)
        
        # Set current state
        controller.hydraulic_solver.current_state.gate_openings[gate_id] = 1.5
        controller.hydraulic_solver.current_state.water_levels = {
            "Junction_1": 98.0,
            "Zone_1": 93.0
        }
        
        # Request transition to AUTO
        with patch.object(controller, 'validate_mode_transition', return_value=True):
            success = await controller.execute_mode_transition(
                gate_id,
                ControlMode.AUTO,
                "SCADA system restored"
            )
        
        assert success is True
        assert controller.gate_registry.get_gate_mode(gate_id) == ControlMode.AUTO
    
    @pytest.mark.asyncio
    async def test_emergency_mode_transition_all_gates(self, integrated_system):
        """Test emergency transition of all gates to safe positions"""
        controller = integrated_system
        
        # Add multiple gates
        gate_ids = ["G1", "G2", "G3"]
        for gate_id in gate_ids:
            controller.gate_registry.add_automated_gate(Mock(
                gate_id=gate_id,
                location=f"Gate {gate_id}",
                control_mode=ControlMode.AUTO,
                scada_tag=f"SCADA.{gate_id}",
                control_equipment=Mock(),
                equipment_status=EquipmentStatus.OPERATIONAL
            ))
        
        # Trigger emergency mode
        emergency_result = await controller.execute_emergency_mode(
            reason="System pressure anomaly detected",
            authorized_by="System Monitor"
        )
        
        assert emergency_result["success"] is True
        assert len(emergency_result["affected_gates"]) == 3
        
        # Verify all gates transitioned
        for gate_id in gate_ids:
            mode = controller.gate_registry.get_gate_mode(gate_id)
            assert mode in [ControlMode.MANUAL, ControlMode.FAILED]
    
    @pytest.mark.asyncio
    async def test_gradual_transition_during_active_flow(self, integrated_system):
        """Test gradual transition while maintaining downstream flow"""
        controller = integrated_system
        gate_id = "G_RES_J1"
        
        # Set initial conditions with active flow
        controller.hydraulic_solver.current_state.gate_openings[gate_id] = 2.0
        controller.hydraulic_solver.current_state.gate_flows[gate_id] = 10.0
        controller.hydraulic_solver.current_state.node_demands = {
            "Zone_1": 5.0,
            "Zone_2": 4.0
        }
        
        # Create transition plan
        plan = await controller.transition_controller.create_transition_plan(
            gate_id,
            current_opening=2.0,
            target_opening=1.0,  # Reduce opening
            strategy=TransitionStrategy.S_CURVE,
            maintain_downstream_flow=True
        )
        
        assert plan is not None
        assert len(plan.steps) > 5  # Should have multiple steps
        assert plan.duration_s >= 60  # Minimum transition time
        
        # Execute transition
        result = await controller.transition_controller.execute_transition(plan)
        
        assert result["completed"] is True
        assert result["final_opening"] == 1.0
        assert len(result["anomalies"]) == 0
    
    @pytest.mark.asyncio
    async def test_mode_transition_with_state_preservation(self, integrated_system):
        """Test state preservation during mode transitions"""
        controller = integrated_system
        
        # Capture initial state
        initial_state = await controller.capture_current_state()
        
        # Execute transition
        gate_id = "G_RES_J1"
        controller.gate_registry.update_gate_mode(gate_id, ControlMode.AUTO)
        
        # Transition with state preservation
        with patch.object(controller.state_preservation, 'preserve_state') as mock_preserve:
            await controller.execute_mode_transition(
                gate_id,
                ControlMode.MAINTENANCE,
                "Scheduled maintenance"
            )
            
            # Verify state was preserved
            mock_preserve.assert_called_once()
            call_args = mock_preserve.call_args[0]
            assert call_args[0] == TransitionType.NORMAL_TO_MAINTENANCE
            assert "maintenance" in call_args[1].lower()
    
    @pytest.mark.asyncio
    async def test_coordinated_multi_gate_transition(self, integrated_system):
        """Test coordinated transition of multiple gates"""
        controller = integrated_system
        
        # Setup multiple connected gates
        gate_pairs = [
            ("G_MAIN", "G_BRANCH1"),
            ("G_MAIN", "G_BRANCH2")
        ]
        
        for upstream, downstream in gate_pairs:
            controller.gate_registry.add_automated_gate(Mock(
                gate_id=upstream,
                control_mode=ControlMode.AUTO
            ))
            controller.gate_registry.add_automated_gate(Mock(
                gate_id=downstream,
                control_mode=ControlMode.AUTO
            ))
        
        # Plan coordinated transition
        transition_plan = await controller.plan_coordinated_transition(
            gates_to_transition=["G_MAIN", "G_BRANCH1", "G_BRANCH2"],
            target_mode=ControlMode.MANUAL,
            coordination_strategy="upstream_first"
        )
        
        assert len(transition_plan["sequence"]) == 3
        assert transition_plan["sequence"][0] == "G_MAIN"  # Upstream first
        
        # Execute coordinated transition
        result = await controller.execute_coordinated_transition(transition_plan)
        
        assert result["success"] is True
        assert all(controller.gate_registry.get_gate_mode(g) == ControlMode.MANUAL 
                  for g in ["G_MAIN", "G_BRANCH1", "G_BRANCH2"])
    
    @pytest.mark.asyncio
    async def test_transition_rollback_on_failure(self, integrated_system):
        """Test rollback of transition on failure"""
        controller = integrated_system
        gate_id = "G_RES_J1"
        
        # Start in AUTO mode
        controller.gate_registry.update_gate_mode(gate_id, ControlMode.AUTO)
        original_opening = 2.0
        controller.hydraulic_solver.current_state.gate_openings[gate_id] = original_opening
        
        # Simulate failure during transition
        with patch.object(controller, '_execute_gate_movement', 
                         side_effect=Exception("Movement failed")):
            result = await controller.execute_mode_transition(
                gate_id,
                ControlMode.MANUAL,
                "Test transition"
            )
        
        # Verify rollback
        assert result is False
        assert controller.gate_registry.get_gate_mode(gate_id) == ControlMode.AUTO
        assert controller.hydraulic_solver.current_state.gate_openings[gate_id] == original_opening
    
    @pytest.mark.asyncio
    async def test_transition_with_downstream_impact_analysis(self, integrated_system):
        """Test transition includes downstream impact analysis"""
        controller = integrated_system
        gate_id = "G_RES_J1"
        
        # Setup downstream dependencies
        controller.hydraulic_solver.current_state.node_demands = {
            "Zone_1": 3.0,
            "Zone_2": 2.5,
            "Zone_3": 1.5
        }
        
        # Analyze impact before transition
        impact_analysis = await controller.analyze_transition_impact(
            gate_id,
            from_mode=ControlMode.AUTO,
            to_mode=ControlMode.MANUAL
        )
        
        assert "affected_zones" in impact_analysis
        assert len(impact_analysis["affected_zones"]) > 0
        assert "service_interruption_risk" in impact_analysis
        assert "recommended_actions" in impact_analysis
        
        # Execute transition only if impact is acceptable
        if impact_analysis["service_interruption_risk"] == "low":
            success = await controller.execute_mode_transition(
                gate_id,
                ControlMode.MANUAL,
                "Acceptable impact"
            )
            assert success is True
    
    @pytest.mark.asyncio
    async def test_automatic_recovery_from_failed_state(self, integrated_system):
        """Test automatic recovery attempts from FAILED state"""
        controller = integrated_system
        gate_id = "G_RES_J1"
        
        # Put gate in FAILED state
        controller.gate_registry.update_gate_mode(gate_id, ControlMode.FAILED)
        controller.gate_registry.automated_gates[gate_id].consecutive_failures = 5
        
        # Start recovery monitoring
        recovery_task = asyncio.create_task(
            controller.monitor_failed_gate_recovery(gate_id)
        )
        
        # Simulate successful communication after delay
        await asyncio.sleep(0.5)
        controller.gate_registry.record_communication(gate_id, success=True)
        
        # Wait for recovery
        await asyncio.sleep(0.5)
        recovery_task.cancel()
        
        # Verify recovery
        mode = controller.gate_registry.get_gate_mode(gate_id)
        assert mode in [ControlMode.AUTO, ControlMode.MANUAL]
        assert controller.gate_registry.automated_gates[gate_id].consecutive_failures == 0