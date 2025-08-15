"""
Unit tests for Enhanced Hydraulic Solver
Tests iterative solving, network calculations, and dual-mode integration
"""

import pytest
import numpy as np
from datetime import datetime
from unittest.mock import Mock, patch

from core.enhanced_hydraulic_solver import (
    EnhancedHydraulicSolver, NetworkNode, NetworkNodeType,
    CanalSection, HydraulicState, SolverSettings
)
from core.gate_registry import GateRegistry, ControlMode


class TestEnhancedHydraulicSolver:
    """Test suite for enhanced hydraulic solver"""
    
    def test_solver_initialization(self, mock_network_config, gate_registry):
        """Test solver initialization with network config"""
        solver = EnhancedHydraulicSolver(mock_network_config, gate_registry)
        
        # Verify nodes loaded
        assert len(solver.nodes) == 4
        assert "Reservoir" in solver.nodes
        assert solver.nodes["Reservoir"].node_type == NetworkNodeType.RESERVOIR
        
        # Verify gates loaded
        assert len(solver.gates) == 2
        assert "G_RES_J1" in solver.gates
        
        # Verify canals loaded
        assert len(solver.canals) == 1
        assert "C_RES_J1" in solver.canals
    
    def test_initial_state_setup(self, mock_network_config, gate_registry):
        """Test initial hydraulic state setup"""
        solver = EnhancedHydraulicSolver(mock_network_config, gate_registry)
        
        # Set initial conditions
        initial_levels = {"Reservoir": 105.0}
        solver.set_initial_conditions(initial_levels)
        
        assert solver.current_state.water_levels["Reservoir"] == 105.0
        # Other nodes should have reasonable initial levels
        assert solver.current_state.water_levels["Junction_1"] > 0
    
    def test_mass_balance_calculation(self, mock_network_config, gate_registry):
        """Test mass balance at nodes"""
        solver = EnhancedHydraulicSolver(mock_network_config, gate_registry)
        
        # Set up a test state
        solver.current_state.water_levels = {
            "Reservoir": 105.0,
            "Junction_1": 98.0,
            "Zone_1": 93.0,
            "Zone_2": 91.0
        }
        solver.current_state.gate_flows = {
            "G_RES_J1": 10.0,  # Inflow to Junction_1
            "G_J1_Z1": 4.0     # Outflow from Junction_1
        }
        solver.current_state.node_demands = {
            "Zone_1": 2.5,
            "Zone_2": 3.0
        }
        
        # Calculate mass balance at Junction_1
        inflows, outflows = solver._calculate_node_flows("Junction_1")
        
        assert inflows == 10.0  # From G_RES_J1
        assert outflows == 4.0  # To G_J1_Z1
        assert (inflows - outflows) == 6.0  # Net inflow
    
    def test_iterative_solving(self, mock_network_config, gate_registry, calibrated_hydraulics):
        """Test iterative hydraulic solving"""
        solver = EnhancedHydraulicSolver(mock_network_config, gate_registry)
        solver.hydraulics = calibrated_hydraulics
        
        # Set initial conditions
        solver.set_initial_conditions({"Reservoir": 105.0})
        
        # Set gate openings
        gate_openings = {
            "G_RES_J1": 2.0,
            "G_J1_Z1": 1.5
        }
        
        # Set demands
        demands = {
            "Zone_1": 2.5,
            "Zone_2": 3.0
        }
        
        # Solve
        state = solver.solve_steady_state(gate_openings, demands)
        
        assert state.convergence_achieved is True
        assert state.iterations > 0
        assert state.max_error < solver.settings.convergence_tolerance_m
        
        # Verify water levels are reasonable
        assert state.water_levels["Reservoir"] > state.water_levels["Junction_1"]
        assert state.water_levels["Junction_1"] > state.water_levels["Zone_1"]
    
    def test_convergence_failure(self, mock_network_config, gate_registry):
        """Test handling of convergence failure"""
        solver = EnhancedHydraulicSolver(mock_network_config, gate_registry)
        solver.settings.max_iterations = 5  # Force early termination
        
        # Set impossible conditions (huge demands)
        gate_openings = {"G_RES_J1": 0.1, "G_J1_Z1": 0.1}  # Very small openings
        demands = {"Zone_1": 100.0, "Zone_2": 100.0}  # Huge demands
        
        state = solver.solve_steady_state(gate_openings, demands)
        
        assert state.convergence_achieved is False
        assert state.iterations == 5
        assert len(state.warnings) > 0
    
    def test_canal_flow_calculation(self, mock_network_config, gate_registry):
        """Test Manning's equation for canal flow"""
        solver = EnhancedHydraulicSolver(mock_network_config, gate_registry)
        
        # Test canal flow calculation
        canal = solver.canals["C_RES_J1"]
        upstream_level = 105.0
        downstream_level = 98.0
        
        flow = solver._calculate_canal_flow(
            canal, upstream_level, downstream_level
        )
        
        assert flow > 0  # Flow in positive direction
        
        # Test reverse flow
        reverse_flow = solver._calculate_canal_flow(
            canal, downstream_level, upstream_level
        )
        
        assert reverse_flow < 0  # Negative flow
    
    def test_simulate_gate_change(self, mock_network_config, gate_registry, calibrated_hydraulics):
        """Test simulation of gate position changes"""
        solver = EnhancedHydraulicSolver(mock_network_config, gate_registry)
        solver.hydraulics = calibrated_hydraulics
        
        # Set initial steady state
        initial_openings = {"G_RES_J1": 2.0, "G_J1_Z1": 1.5}
        demands = {"Zone_1": 2.5, "Zone_2": 3.0}
        
        solver.solve_steady_state(initial_openings, demands)
        
        # Simulate gate change
        states = solver.simulate_gate_change(
            "G_RES_J1", 
            target_opening=3.0,
            duration_s=300  # 5 minutes
        )
        
        assert len(states) > 1
        assert states[0].gate_openings["G_RES_J1"] == 2.0
        assert states[-1].gate_openings["G_RES_J1"] == 3.0
        
        # Flow should increase with larger opening
        assert states[-1].gate_flows["G_RES_J1"] > states[0].gate_flows["G_RES_J1"]
    
    def test_check_velocity_constraints(self, mock_network_config, gate_registry):
        """Test velocity constraint checking"""
        solver = EnhancedHydraulicSolver(mock_network_config, gate_registry)
        
        # Create state with high flow
        state = HydraulicState(
            timestamp=datetime.now(),
            water_levels={"Reservoir": 105.0, "Junction_1": 98.0},
            gate_flows={"G_RES_J1": 50.0},  # Very high flow
            gate_openings={"G_RES_J1": 4.0},
            canal_flows={"C_RES_J1": 50.0},
            node_demands={}
        )
        
        violations = solver.check_velocity_constraints(state)
        
        assert len(violations) > 0
        assert any("velocity" in str(v).lower() for v in violations)
    
    def test_check_depth_constraints(self, mock_network_config, gate_registry):
        """Test water depth constraint checking"""
        solver = EnhancedHydraulicSolver(mock_network_config, gate_registry)
        
        # Create state with extreme water levels
        state = HydraulicState(
            timestamp=datetime.now(),
            water_levels={
                "Reservoir": 105.0,
                "Junction_1": 98.0,
                "Zone_1": 88.0,  # Below minimum operational depth
                "Zone_2": 95.0   # Above maximum depth
            },
            gate_flows={},
            gate_openings={},
            canal_flows={},
            node_demands={}
        )
        
        violations = solver.check_depth_constraints(state)
        
        assert len(violations) >= 2
        assert any("below minimum" in str(v).lower() for v in violations)
        assert any("above maximum" in str(v).lower() for v in violations)
    
    def test_adaptive_relaxation(self, mock_network_config, gate_registry):
        """Test adaptive relaxation factor adjustment"""
        solver = EnhancedHydraulicSolver(mock_network_config, gate_registry)
        solver.settings.use_adaptive_relaxation = True
        
        # Simulate oscillating convergence
        errors = [1.0, 0.8, 0.9, 0.7, 0.8]  # Oscillating
        
        for error in errors:
            solver._update_relaxation_factor(error)
        
        # Relaxation factor should decrease due to oscillation
        assert solver.settings.relaxation_factor < 0.7
    
    def test_dual_mode_gate_handling(self, mock_network_config, gate_registry):
        """Test handling of automated vs manual gates in solving"""
        solver = EnhancedHydraulicSolver(mock_network_config, gate_registry)
        
        # Set one gate to manual mode
        gate_registry.update_gate_mode("G_RES_J1", ControlMode.MANUAL)
        
        # Manual gates should use reported positions
        manual_positions = {"G_RES_J1": 1.8}  # Manually reported position
        auto_commands = {"G_J1_Z1": 2.0}  # Automated command
        
        effective_openings = solver._get_effective_gate_openings(
            auto_commands, manual_positions
        )
        
        assert effective_openings["G_RES_J1"] == 1.8  # Uses manual position
        assert effective_openings["G_J1_Z1"] == 2.0   # Uses auto command
    
    def test_emergency_state_handling(self, mock_network_config, gate_registry):
        """Test emergency state detection and handling"""
        solver = EnhancedHydraulicSolver(mock_network_config, gate_registry)
        
        # Create sudden water level change
        previous_state = HydraulicState(
            timestamp=datetime.now(),
            water_levels={"Junction_1": 98.0},
            gate_flows={},
            gate_openings={},
            canal_flows={},
            node_demands={}
        )
        
        current_state = HydraulicState(
            timestamp=datetime.now(),
            water_levels={"Junction_1": 99.0},  # 1m sudden rise!
            gate_flows={},
            gate_openings={},
            canal_flows={},
            node_demands={}
        )
        
        is_emergency = solver._detect_emergency_condition(
            previous_state, current_state
        )
        
        assert is_emergency is True