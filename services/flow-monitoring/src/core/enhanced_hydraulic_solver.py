#!/usr/bin/env python3
"""
Enhanced Hydraulic Solver for Munbon Irrigation Network
Integrates calibrated gate equations, drop structures, and dual-mode control
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from enum import Enum

from .calibrated_gate_hydraulics import (
    CalibratedGateHydraulics, GateProperties, GateCalibration, 
    HydraulicConditions, FlowCalculationResult, GateType
)
from .gate_registry import GateRegistry, ControlMode

logger = logging.getLogger(__name__)


class NetworkNodeType(Enum):
    """Types of nodes in the irrigation network"""
    RESERVOIR = "reservoir"
    JUNCTION = "junction"
    DELIVERY = "delivery"
    TERMINAL = "terminal"


@dataclass
class NetworkNode:
    """Node in the irrigation network"""
    node_id: str
    node_type: NetworkNodeType
    elevation_m: float  # Ground/invert elevation
    surface_area_m2: float = 1000.0  # For storage calculations
    demand_m3s: float = 0.0  # Water demand at this node
    min_depth_m: float = 0.1  # Minimum operational depth
    max_depth_m: float = 5.0  # Maximum allowed depth


@dataclass
class CanalSection:
    """Canal/channel properties between nodes"""
    section_id: str
    upstream_node: str
    downstream_node: str
    length_m: float
    bottom_width_m: float
    side_slope: float  # H:V ratio
    manning_n: float
    bed_slope: float
    has_transition: bool = False
    transition_loss_coeff: float = 0.1


@dataclass
class HydraulicState:
    """Current hydraulic state of the network"""
    timestamp: datetime
    water_levels: Dict[str, float]  # node_id -> water surface elevation
    gate_flows: Dict[str, float]  # gate_id -> flow rate
    gate_openings: Dict[str, float]  # gate_id -> opening
    canal_flows: Dict[str, float]  # section_id -> flow rate
    node_demands: Dict[str, float]  # node_id -> demand
    convergence_achieved: bool = False
    iterations: int = 0
    max_error: float = 0.0
    warnings: List[str] = field(default_factory=list)


@dataclass
class SolverSettings:
    """Solver configuration parameters"""
    max_iterations: int = 100
    convergence_tolerance_m: float = 0.001  # 1mm
    relaxation_factor: float = 0.7
    min_time_step_s: float = 60.0
    max_time_step_s: float = 300.0
    use_adaptive_relaxation: bool = True
    check_mass_balance: bool = True
    mass_balance_tolerance: float = 0.01  # 1% error allowed


class EnhancedHydraulicSolver:
    """
    Advanced hydraulic solver with calibrated gate equations and dual-mode control
    """
    
    def __init__(self, network_config: Dict, gate_registry: GateRegistry, 
                 solver_settings: Optional[SolverSettings] = None):
        """
        Initialize enhanced hydraulic solver
        
        Args:
            network_config: Network topology and properties
            gate_registry: Gate registry with auto/manual classification
            solver_settings: Solver parameters
        """
        self.gate_registry = gate_registry
        self.hydraulics = CalibratedGateHydraulics()
        self.settings = solver_settings or SolverSettings()
        
        # Network components
        self.nodes: Dict[str, NetworkNode] = {}
        self.gates: Dict[str, Tuple[str, str]] = {}  # gate_id -> (upstream, downstream)
        self.canals: Dict[str, CanalSection] = {}
        
        # Current state
        self.current_state: Optional[HydraulicState] = None
        
        # Load network configuration
        self._load_network_config(network_config)
        
        # Initialize gate properties and calibrations
        self._initialize_gates()
        
        logger.info(f"Enhanced hydraulic solver initialized with {len(self.nodes)} nodes, "
                   f"{len(self.gates)} gates, {len(self.canals)} canal sections")
    
    def _load_network_config(self, config: Dict):
        """Load network topology from configuration"""
        # Load nodes
        for node_data in config.get("nodes", []):
            node = NetworkNode(**node_data)
            self.nodes[node.node_id] = node
        
        # Load gates with connections
        for gate_data in config.get("gates", []):
            gate_id = gate_data["gate_id"]
            upstream = gate_data["upstream_node"]
            downstream = gate_data["downstream_node"]
            self.gates[gate_id] = (upstream, downstream)
            
            # Create gate properties
            props = GateProperties(
                gate_id=gate_id,
                gate_type=GateType(gate_data.get("gate_type", "sluice_gate")),
                width_m=gate_data["width_m"],
                height_m=gate_data["height_m"],
                sill_elevation_m=gate_data["sill_elevation_m"],
                has_drop_structure=gate_data.get("has_drop_structure", False),
                drop_height_m=gate_data.get("drop_height_m", 0.0),
                drop_type=gate_data.get("drop_type", "none")
            )
            self.hydraulics.add_gate_properties(props)
            
            # Add calibration if provided
            if "calibration" in gate_data:
                cal_data = gate_data["calibration"]
                calibration = GateCalibration(
                    gate_id=gate_id,
                    K1=cal_data["K1"],
                    K2=cal_data["K2"],
                    confidence=cal_data.get("confidence", 0.9),
                    calibration_date=datetime.fromisoformat(cal_data["date"]) if "date" in cal_data else None
                )
                self.hydraulics.add_gate_calibration(calibration)
        
        # Load canal sections
        for canal_data in config.get("canals", []):
            canal = CanalSection(**canal_data)
            self.canals[canal.section_id] = canal
    
    def _initialize_gates(self):
        """Initialize gate properties from registry"""
        # Add automated gates
        for gate_id in self.gate_registry.get_automated_gates_list():
            if gate_id not in self.gates:
                logger.warning(f"Automated gate {gate_id} not found in network topology")
        
        # Verify all gates in topology are in registry
        for gate_id in self.gates:
            if not (self.gate_registry.is_automated(gate_id) or 
                   gate_id in self.gate_registry.manual_gates):
                logger.warning(f"Gate {gate_id} not found in gate registry")
    
    def set_initial_conditions(self, water_levels: Dict[str, float], 
                             gate_openings: Dict[str, float]):
        """Set initial water levels and gate openings"""
        # Initialize state
        self.current_state = HydraulicState(
            timestamp=datetime.now(),
            water_levels=water_levels.copy(),
            gate_flows={},
            gate_openings=gate_openings.copy(),
            canal_flows={},
            node_demands={}
        )
        
        # Set default water levels for missing nodes
        for node_id, node in self.nodes.items():
            if node_id not in self.current_state.water_levels:
                # Default to minimum operational level
                self.current_state.water_levels[node_id] = node.elevation_m + node.min_depth_m
        
        logger.info("Initial conditions set for hydraulic solver")
    
    def update_demands(self, demands: Dict[str, float]):
        """Update water demands at delivery nodes"""
        if self.current_state:
            self.current_state.node_demands.update(demands)
        
        # Update node objects
        for node_id, demand in demands.items():
            if node_id in self.nodes:
                self.nodes[node_id].demand_m3s = demand
    
    def calculate_gate_flow(self, gate_id: str) -> float:
        """Calculate flow through a gate using calibrated equation"""
        if gate_id not in self.gates:
            return 0.0
        
        upstream, downstream = self.gates[gate_id]
        
        # Get current conditions
        conditions = HydraulicConditions(
            upstream_water_level_m=self.current_state.water_levels.get(upstream, 0),
            downstream_water_level_m=self.current_state.water_levels.get(downstream, 0),
            gate_opening_m=self.current_state.gate_openings.get(gate_id, 0),
            timestamp=datetime.now()
        )
        
        # Check if gate is operational
        gate_mode = self.gate_registry.get_gate_mode(gate_id)
        if gate_mode == ControlMode.FAILED:
            self.current_state.warnings.append(f"Gate {gate_id} is in FAILED mode")
            return 0.0
        
        # Calculate flow using calibrated hydraulics
        result = self.hydraulics.calculate_gate_flow(gate_id, conditions)
        
        # Add warnings to state
        if result.warnings:
            self.current_state.warnings.extend([f"Gate {gate_id}: {w}" for w in result.warnings])
        
        return result.flow_rate_m3s
    
    def calculate_canal_flow(self, section_id: str) -> float:
        """Calculate flow in canal section using Manning's equation"""
        if section_id not in self.canals:
            return 0.0
        
        canal = self.canals[section_id]
        
        # Get water levels
        h_upstream = self.current_state.water_levels.get(canal.upstream_node, 0)
        h_downstream = self.current_state.water_levels.get(canal.downstream_node, 0)
        
        # Get node elevations
        z_upstream = self.nodes[canal.upstream_node].elevation_m
        z_downstream = self.nodes[canal.downstream_node].elevation_m
        
        # Calculate depths
        y_upstream = h_upstream - z_upstream
        y_downstream = h_downstream - z_downstream
        
        if y_upstream <= 0 and y_downstream <= 0:
            return 0.0
        
        # Average depth and hydraulic parameters
        y_avg = (y_upstream + y_downstream) / 2
        if y_avg <= 0:
            return 0.0
        
        # Trapezoidal channel geometry
        b = canal.bottom_width_m
        m = canal.side_slope
        
        # Flow area and wetted perimeter
        A = y_avg * (b + m * y_avg)
        P = b + 2 * y_avg * np.sqrt(1 + m**2)
        
        # Hydraulic radius
        R = A / P if P > 0 else 0
        
        # Energy slope (approximate)
        Sf = ((h_upstream - h_downstream) / canal.length_m) - canal.bed_slope
        
        if Sf <= 0:
            # Adverse slope - use minimum slope
            Sf = 0.0001
        
        # Manning's equation: V = (1/n) * R^(2/3) * Sf^(1/2)
        V = (1 / canal.manning_n) * (R ** (2/3)) * (Sf ** 0.5)
        
        # Flow rate
        Q = A * V
        
        return Q
    
    def calculate_node_continuity(self, node_id: str) -> float:
        """
        Calculate flow imbalance at a node (mass balance)
        Returns: inflow - outflow - demand (positive = excess)
        """
        if node_id not in self.nodes:
            return 0.0
        
        inflow = 0.0
        outflow = 0.0
        
        # Sum gate flows
        for gate_id, (upstream, downstream) in self.gates.items():
            flow = self.current_state.gate_flows.get(gate_id, 0)
            
            if downstream == node_id:
                inflow += flow
            elif upstream == node_id:
                outflow += flow
        
        # Sum canal flows
        for section_id, canal in self.canals.items():
            flow = self.current_state.canal_flows.get(section_id, 0)
            
            if canal.downstream_node == node_id:
                inflow += flow
            elif canal.upstream_node == node_id:
                outflow += flow
        
        # Account for demand
        demand = self.nodes[node_id].demand_m3s
        
        # Special handling for reservoir nodes
        if self.nodes[node_id].node_type == NetworkNodeType.RESERVOIR:
            # Reservoir can supply any required flow
            return 0.0
        
        return inflow - outflow - demand
    
    def update_water_level(self, node_id: str, continuity_error: float, dt: float):
        """Update water level based on continuity error"""
        if node_id not in self.nodes:
            return
        
        node = self.nodes[node_id]
        
        # Skip reservoir nodes
        if node.node_type == NetworkNodeType.RESERVOIR:
            return
        
        # Calculate level change
        dh = (continuity_error * dt) / node.surface_area_m2
        
        # Apply with relaxation
        if self.settings.use_adaptive_relaxation:
            # Reduce relaxation factor if oscillating
            if hasattr(self, '_prev_errors') and node_id in self._prev_errors:
                if np.sign(continuity_error) != np.sign(self._prev_errors[node_id]):
                    # Oscillation detected
                    relaxation = self.settings.relaxation_factor * 0.5
                else:
                    relaxation = self.settings.relaxation_factor
            else:
                relaxation = self.settings.relaxation_factor
                self._prev_errors = {}
            
            self._prev_errors[node_id] = continuity_error
        else:
            relaxation = self.settings.relaxation_factor
        
        # Update level
        new_level = self.current_state.water_levels[node_id] + relaxation * dh
        
        # Apply constraints
        min_level = node.elevation_m + node.min_depth_m
        max_level = node.elevation_m + node.max_depth_m
        
        self.current_state.water_levels[node_id] = np.clip(new_level, min_level, max_level)
    
    def solve_steady_state(self, target_demands: Optional[Dict[str, float]] = None) -> HydraulicState:
        """
        Solve for steady-state water levels and flows
        
        Args:
            target_demands: Optional demand overrides
            
        Returns:
            Converged hydraulic state
        """
        if self.current_state is None:
            raise ValueError("Initial conditions not set. Call set_initial_conditions first.")
        
        # Update demands if provided
        if target_demands:
            self.update_demands(target_demands)
        
        # Store initial state for comparison
        initial_levels = self.current_state.water_levels.copy()
        
        # Reset warnings
        self.current_state.warnings = []
        
        # Iterative solution
        converged = False
        iteration = 0
        mass_balance_errors = []
        
        logger.info("Starting steady-state hydraulic solution...")
        
        while iteration < self.settings.max_iterations and not converged:
            iteration += 1
            
            # Store previous levels
            prev_levels = self.current_state.water_levels.copy()
            
            # Step 1: Update all gate flows
            for gate_id in self.gates:
                self.current_state.gate_flows[gate_id] = self.calculate_gate_flow(gate_id)
            
            # Step 2: Update all canal flows
            for section_id in self.canals:
                self.current_state.canal_flows[section_id] = self.calculate_canal_flow(section_id)
            
            # Step 3: Check mass balance at each node
            total_imbalance = 0.0
            node_errors = {}
            
            for node_id in self.nodes:
                if self.nodes[node_id].node_type == NetworkNodeType.RESERVOIR:
                    continue
                
                # Calculate continuity error
                error = self.calculate_node_continuity(node_id)
                node_errors[node_id] = error
                total_imbalance += abs(error)
                
                # Update water level
                self.update_water_level(node_id, error, self.settings.min_time_step_s)
            
            mass_balance_errors.append(total_imbalance)
            
            # Step 4: Check convergence
            max_change = 0.0
            for node_id in self.nodes:
                if self.nodes[node_id].node_type != NetworkNodeType.RESERVOIR:
                    change = abs(self.current_state.water_levels[node_id] - prev_levels[node_id])
                    max_change = max(max_change, change)
            
            # Log progress
            if iteration % 10 == 0 or iteration == 1:
                logger.info(f"Iteration {iteration}: Max level change = {max_change:.4f}m, "
                          f"Mass balance error = {total_imbalance:.3f} m³/s")
            
            # Check convergence criteria
            if max_change < self.settings.convergence_tolerance_m:
                # Additional mass balance check
                if self.settings.check_mass_balance:
                    total_inflow = sum(self.current_state.gate_flows.values()) + \
                                  sum(self.current_state.canal_flows.values())
                    total_demand = sum(node.demand_m3s for node in self.nodes.values())
                    
                    if total_inflow > 0:
                        balance_error = abs(total_inflow - total_demand) / total_inflow
                        if balance_error < self.settings.mass_balance_tolerance:
                            converged = True
                        else:
                            self.current_state.warnings.append(
                                f"Mass balance error {balance_error:.1%} exceeds tolerance"
                            )
                else:
                    converged = True
        
        # Update convergence status
        self.current_state.convergence_achieved = converged
        self.current_state.iterations = iteration
        self.current_state.max_error = max_change
        
        if not converged:
            self.current_state.warnings.append(
                f"Solution did not converge after {iteration} iterations"
            )
        
        # Log final results
        logger.info(f"Hydraulic solution {'converged' if converged else 'stopped'} "
                   f"after {iteration} iterations")
        
        # Check for dry nodes or other issues
        for node_id, node in self.nodes.items():
            if node.node_type == NetworkNodeType.RESERVOIR:
                continue
            
            depth = self.current_state.water_levels[node_id] - node.elevation_m
            if depth < node.min_depth_m * 1.5:
                self.current_state.warnings.append(
                    f"Node {node_id} water depth critically low: {depth:.2f}m"
                )
        
        return self.current_state
    
    def simulate_gate_change(self, gate_id: str, new_opening: float, 
                           transition_time_s: float = 300) -> List[HydraulicState]:
        """
        Simulate gradual gate opening change
        
        Args:
            gate_id: Gate to adjust
            new_opening: Target opening (m)
            transition_time_s: Time for transition
            
        Returns:
            List of states during transition
        """
        if self.current_state is None:
            raise ValueError("No current state available")
        
        if gate_id not in self.gates:
            raise ValueError(f"Gate {gate_id} not found")
        
        # Check if gate is operational
        mode = self.gate_registry.get_gate_mode(gate_id)
        if mode == ControlMode.FAILED:
            logger.warning(f"Cannot adjust failed gate {gate_id}")
            return [self.current_state]
        
        # Get current opening
        current_opening = self.current_state.gate_openings.get(gate_id, 0)
        
        # Calculate steps
        opening_change = new_opening - current_opening
        num_steps = max(int(transition_time_s / self.settings.min_time_step_s), 1)
        
        states = []
        
        for step in range(num_steps + 1):
            # Calculate intermediate opening
            progress = step / num_steps
            intermediate_opening = current_opening + progress * opening_change
            
            # Update gate opening
            self.current_state.gate_openings[gate_id] = intermediate_opening
            
            # Solve hydraulics
            state = self.solve_steady_state()
            states.append(HydraulicState(
                timestamp=state.timestamp,
                water_levels=state.water_levels.copy(),
                gate_flows=state.gate_flows.copy(),
                gate_openings=state.gate_openings.copy(),
                canal_flows=state.canal_flows.copy(),
                node_demands=state.node_demands.copy(),
                convergence_achieved=state.convergence_achieved,
                iterations=state.iterations,
                max_error=state.max_error,
                warnings=state.warnings.copy()
            ))
        
        return states
    
    def export_state(self) -> Dict:
        """Export current hydraulic state"""
        if self.current_state is None:
            return {}
        
        return {
            "timestamp": self.current_state.timestamp.isoformat(),
            "water_levels": self.current_state.water_levels,
            "gate_flows": self.current_state.gate_flows,
            "gate_openings": self.current_state.gate_openings,
            "canal_flows": self.current_state.canal_flows,
            "node_demands": self.current_state.node_demands,
            "convergence": {
                "achieved": self.current_state.convergence_achieved,
                "iterations": self.current_state.iterations,
                "max_error": self.current_state.max_error
            },
            "warnings": self.current_state.warnings
        }