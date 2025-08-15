"""
Unit tests for Gradual Transition Controller
Tests smooth transitions to prevent hydraulic shocks
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from core.gradual_transition_controller import (
    GradualTransitionController, TransitionStrategy, HydraulicCondition,
    TransitionConstraints, GateTransitionPlan, TransitionStep,
    SystemTransitionPlan, TransitionMonitoringData
)


class TestGradualTransitionController:
    """Test suite for gradual transition controller"""
    
    @pytest.fixture
    def mock_hydraulic_solver(self):
        """Mock hydraulic solver for testing"""
        solver = Mock()
        solver.simulate_gate_change = AsyncMock()
        solver.current_state = Mock()
        solver.current_state.water_levels = {
            "Reservoir": 105.0,
            "Junction_1": 98.0,
            "Zone_1": 93.0
        }
        solver.current_state.gate_flows = {
            "G_RES_J1": 10.0,
            "G_J1_Z1": 5.0
        }
        return solver
    
    @pytest.fixture
    def transition_controller(self, mock_hydraulic_solver):
        """Create transition controller instance"""
        constraints = TransitionConstraints(
            max_gate_speed_percent_per_sec=5.0,
            max_flow_change_m3s_per_min=0.5,
            max_level_change_m_per_min=0.1,
            max_velocity_m_per_s=2.0
        )
        return GradualTransitionController(mock_hydraulic_solver, constraints)
    
    def test_linear_transition_profile(self, transition_controller):
        """Test linear transition profile generation"""
        plan = transition_controller.create_gate_transition_plan(
            gate_id="G_RES_J1",
            start_position=1.0,
            target_position=3.0,
            strategy=TransitionStrategy.LINEAR,
            duration_s=120.0
        )
        
        assert plan.gate_id == "G_RES_J1"
        assert plan.start_position == 1.0
        assert plan.target_position == 3.0
        assert plan.duration_s == 120.0
        assert len(plan.steps) > 0
        
        # Verify linear progression
        positions = [step.gate_position for step in plan.steps]
        differences = np.diff(positions)
        assert np.allclose(differences, differences[0], rtol=0.01)
    
    def test_s_curve_transition_profile(self, transition_controller):
        """Test S-curve transition profile generation"""
        plan = transition_controller.create_gate_transition_plan(
            gate_id="G_RES_J1",
            start_position=0.5,
            target_position=2.5,
            strategy=TransitionStrategy.S_CURVE,
            duration_s=180.0
        )
        
        positions = [step.gate_position for step in plan.steps]
        
        # S-curve should start slow, accelerate, then decelerate
        early_diff = positions[1] - positions[0]
        mid_diff = positions[len(positions)//2] - positions[len(positions)//2 - 1]
        late_diff = positions[-1] - positions[-2]
        
        assert mid_diff > early_diff  # Acceleration
        assert mid_diff > late_diff   # Deceleration
    
    def test_speed_constraint_enforcement(self, transition_controller):
        """Test that gate speed constraints are enforced"""
        # Request very fast transition
        plan = transition_controller.create_gate_transition_plan(
            gate_id="G_RES_J1",
            start_position=0.0,
            target_position=4.0,  # 4m change
            strategy=TransitionStrategy.LINEAR,
            duration_s=10.0  # Only 10 seconds - too fast!
        )
        
        # Controller should extend duration to meet speed constraints
        assert plan.duration_s > 10.0
        assert "speed_limit" in plan.constraints_applied
        
        # Verify max speed not exceeded
        for i in range(1, len(plan.steps)):
            position_change = abs(plan.steps[i].gate_position - plan.steps[i-1].gate_position)
            time_change = plan.steps[i].time_offset_s - plan.steps[i-1].time_offset_s
            speed = position_change / time_change if time_change > 0 else 0
            
            # Convert to percentage (assuming 4m max height)
            speed_percent = (speed / 4.0) * 100
            assert speed_percent <= transition_controller.constraints.max_gate_speed_percent_per_sec + 0.1
    
    @pytest.mark.asyncio
    async def test_hydraulic_impact_monitoring(self, transition_controller, mock_hydraulic_solver):
        """Test monitoring of hydraulic impacts during transition"""
        # Set up mock simulation results
        mock_states = [
            Mock(water_levels={"Junction_1": 98.0}),
            Mock(water_levels={"Junction_1": 98.5}),  # Rising
            Mock(water_levels={"Junction_1": 99.0})   # Too fast!
        ]
        mock_hydraulic_solver.simulate_gate_change.return_value = mock_states
        
        plan = GateTransitionPlan(
            gate_id="G_RES_J1",
            start_position=1.0,
            target_position=3.0,
            strategy=TransitionStrategy.LINEAR,
            duration_s=60.0,
            steps=[TransitionStep(i, i*10, 1.0 + i*0.5, 0, 5.0) for i in range(5)]
        )
        
        # Execute with monitoring
        monitoring_data = await transition_controller.execute_transition_with_monitoring(plan)
        
        assert len(monitoring_data) > 0
        # Should detect rapid level change
        assert any(
            HydraulicCondition.SHOCK_RISK in data.hydraulic_condition.value 
            for data in monitoring_data
        )
    
    def test_multi_gate_coordination(self, transition_controller):
        """Test coordinated transition of multiple gates"""
        gate_changes = {
            "G_RES_J1": (1.0, 2.0),  # From 1m to 2m
            "G_J1_Z1": (1.5, 0.5)    # From 1.5m to 0.5m
        }
        
        system_plan = transition_controller.create_system_transition_plan(
            gate_changes,
            coordination_strategy="balanced_flow"
        )
        
        assert len(system_plan.gate_plans) == 2
        assert "G_RES_J1" in system_plan.gate_plans
        assert "G_J1_Z1" in system_plan.gate_plans
        
        # Verify coordination - closing gate should start after opening gate
        opening_plan = system_plan.gate_plans["G_RES_J1"]
        closing_plan = system_plan.gate_plans["G_J1_Z1"]
        
        assert closing_plan.steps[0].time_offset_s >= opening_plan.steps[0].time_offset_s
    
    def test_adaptive_transition_adjustment(self, transition_controller):
        """Test adaptive strategy that adjusts based on system response"""
        plan = transition_controller.create_gate_transition_plan(
            gate_id="G_RES_J1",
            start_position=1.0,
            target_position=3.0,
            strategy=TransitionStrategy.ADAPTIVE,
            duration_s=120.0
        )
        
        # Adaptive plan should have hold points for observation
        hold_steps = [step for step in plan.steps if step.hold_duration_s > 0]
        assert len(hold_steps) > 0
        assert any("observe" in step.notes.lower() for step in hold_steps)
    
    def test_emergency_stop_during_transition(self, transition_controller):
        """Test emergency stop capability during transition"""
        plan = GateTransitionPlan(
            gate_id="G_RES_J1",
            start_position=1.0,
            target_position=3.0,
            strategy=TransitionStrategy.LINEAR,
            duration_s=60.0,
            steps=[TransitionStep(i, i*10, 1.0 + i*0.5, 0, 5.0) for i in range(7)]
        )
        
        # Trigger emergency stop at step 3
        stopped_position = transition_controller.emergency_stop_transition(
            plan, current_step=3
        )
        
        assert stopped_position == plan.steps[3].gate_position
        assert transition_controller.is_emergency_stop_active()
    
    def test_flow_rate_constraint(self, transition_controller):
        """Test flow rate change constraints"""
        # Create plan that would cause rapid flow change
        plan = transition_controller.create_gate_transition_plan(
            gate_id="G_RES_J1",
            start_position=0.1,  # Nearly closed
            target_position=4.0,  # Fully open - huge flow change!
            strategy=TransitionStrategy.LINEAR,
            duration_s=60.0
        )
        
        # Should extend duration to limit flow rate change
        assert plan.duration_s > 60.0
        assert "flow_rate_limit" in plan.constraints_applied
    
    def test_oscillation_detection(self, transition_controller):
        """Test detection of hydraulic oscillations"""
        monitoring_data = [
            TransitionMonitoringData(
                timestamp=datetime.now(),
                gate_positions={"G_RES_J1": 2.0},
                water_levels={"Junction_1": 98.0},
                flow_rates={"G_RES_J1": 10.0},
                velocities={"C_RES_J1": 1.0},
                hydraulic_condition=HydraulicCondition.STABLE
            ),
            TransitionMonitoringData(
                timestamp=datetime.now() + timedelta(seconds=10),
                gate_positions={"G_RES_J1": 2.1},
                water_levels={"Junction_1": 99.0},  # Rising
                flow_rates={"G_RES_J1": 11.0},
                velocities={"C_RES_J1": 1.2},
                hydraulic_condition=HydraulicCondition.STABLE
            ),
            TransitionMonitoringData(
                timestamp=datetime.now() + timedelta(seconds=20),
                gate_positions={"G_RES_J1": 2.2},
                water_levels={"Junction_1": 97.5},  # Falling - oscillation!
                flow_rates={"G_RES_J1": 9.0},
                velocities={"C_RES_J1": 0.8},
                hydraulic_condition=HydraulicCondition.STABLE
            )
        ]
        
        condition = transition_controller.analyze_hydraulic_condition(monitoring_data)
        
        assert condition in [HydraulicCondition.MINOR_OSCILLATION, 
                           HydraulicCondition.MAJOR_OSCILLATION]
    
    def test_transition_rollback(self, transition_controller):
        """Test ability to rollback a transition on failure"""
        original_position = 1.0
        plan = GateTransitionPlan(
            gate_id="G_RES_J1",
            start_position=original_position,
            target_position=3.0,
            strategy=TransitionStrategy.LINEAR,
            duration_s=60.0,
            steps=[TransitionStep(i, i*10, 1.0 + i*0.5, 0, 5.0) for i in range(7)]
        )
        
        # Simulate failure at step 4
        rollback_plan = transition_controller.create_rollback_plan(
            plan, 
            failed_at_step=4,
            target_position=original_position
        )
        
        assert rollback_plan.target_position == original_position
        assert rollback_plan.strategy == TransitionStrategy.S_CURVE  # Gentle rollback
        assert "rollback" in rollback_plan.steps[0].notes.lower()