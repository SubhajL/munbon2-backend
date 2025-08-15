import numpy as np
from scipy.optimize import minimize, LinearConstraint, NonlinearConstraint
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging
from ..models.channel import Gate, GateType, NetworkTopology
from ..models.optimization import (
    GateSetting, ZoneDeliveryRequest, FlowSplitOptimization,
    OptimizationObjective
)
from ..config.settings import settings
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class GateFlowCharacteristics:
    """Flow characteristics for a gate"""
    gate_id: str
    discharge_coefficient: float
    max_flow: float
    min_flow: float
    upstream_channel_capacity: float
    downstream_channel_capacity: float
    gate_authority: float  # Ability to control flow (0-1)


class FlowSplitter:
    """Optimize flow distribution through automated gates"""
    
    def __init__(self, network: NetworkTopology):
        self.network = network
        self.automated_gates = [g for g in network.gates if g.gate_type == GateType.AUTOMATED]
        self.gate_characteristics = self._analyze_gate_characteristics()
        
    def optimize_flow_split(
        self,
        total_inflow: float,
        zone_requests: List[ZoneDeliveryRequest],
        objective: OptimizationObjective = OptimizationObjective.BALANCED,
        current_gate_settings: Optional[Dict[str, float]] = None
    ) -> FlowSplitOptimization:
        """
        Optimize flow distribution through automated gates
        
        Args:
            total_inflow: Total available flow in m³/s
            zone_requests: Water demands for each zone
            objective: Optimization objective
            current_gate_settings: Current gate openings (for smooth transitions)
        
        Returns:
            Optimized flow split with gate settings
        """
        start_time = datetime.now()
        
        # Validate requests
        total_demand = sum(req.required_flow_rate for req in zone_requests)
        if total_demand > total_inflow * 1.1:  # Allow 10% over-allocation
            logger.warning(
                f"Total demand ({total_demand:.2f}) exceeds available flow ({total_inflow:.2f})"
            )
        
        # Set up optimization problem
        n_gates = len(self.automated_gates)
        n_zones = len(zone_requests)
        
        # Decision variables: gate openings (0-1)
        x0 = self._get_initial_guess(current_gate_settings, zone_requests, total_inflow)
        
        # Bounds: gate openings between 0 and 1
        bounds = [(0, 1) for _ in range(n_gates)]
        
        # Constraints
        constraints = self._build_constraints(total_inflow, zone_requests)
        
        # Objective function based on selected objective
        if objective == OptimizationObjective.MINIMIZE_TRAVEL_TIME:
            objective_func = self._objective_minimize_travel_time
        elif objective == OptimizationObjective.MAXIMIZE_EFFICIENCY:
            objective_func = self._objective_maximize_efficiency
        elif objective == OptimizationObjective.MINIMIZE_ENERGY_LOSS:
            objective_func = self._objective_minimize_energy_loss
        else:  # BALANCED
            objective_func = self._objective_balanced
        
        # Solve optimization
        result = minimize(
            lambda x: objective_func(x, zone_requests),
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={
                'ftol': settings.optimization_tolerance,
                'maxiter': settings.max_iterations,
                'disp': False
            }
        )
        
        if not result.success:
            logger.warning(f"Optimization did not converge: {result.message}")
        
        # Extract results
        gate_settings = self._extract_gate_settings(result.x, total_inflow)
        zone_flows = self._calculate_zone_flows(gate_settings, zone_requests)
        efficiency = self._calculate_efficiency(zone_flows, zone_requests, total_inflow)
        
        optimization_time = (datetime.now() - start_time).total_seconds()
        
        return FlowSplitOptimization(
            optimization_id=f"split_{datetime.now().isoformat()}",
            timestamp=datetime.now(),
            objective=objective,
            total_inflow=total_inflow,
            zone_allocations=zone_flows,
            gate_settings=gate_settings,
            efficiency=efficiency,
            convergence_iterations=result.nit if hasattr(result, 'nit') else 0,
            optimization_time=optimization_time
        )
    
    def _analyze_gate_characteristics(self) -> Dict[str, GateFlowCharacteristics]:
        """Analyze flow characteristics for each automated gate"""
        characteristics = {}
        
        for gate in self.automated_gates:
            # Get connected channels
            upstream_channel = next(
                (c for c in self.network.channels if c.channel_id == gate.upstream_channel_id),
                None
            )
            downstream_channel = next(
                (c for c in self.network.channels if c.channel_id == gate.downstream_channel_id),
                None
            )
            
            # Calculate flow capacities
            discharge_coeff = 0.6  # Standard for sluice gates
            
            # Maximum flow through gate (orifice flow equation)
            # Q = Cd * A * sqrt(2 * g * h)
            max_head = 2.0  # Assume 2m maximum head
            gate_area = gate.max_opening * 5.0  # Assume 5m width
            max_flow = discharge_coeff * gate_area * np.sqrt(2 * settings.gravity * max_head)
            
            # Channel capacities
            upstream_capacity = upstream_channel.capacity if upstream_channel else max_flow
            downstream_capacity = downstream_channel.capacity if downstream_channel else max_flow
            
            # Gate authority (how well it can control flow)
            authority = 1.0
            if upstream_channel and downstream_channel:
                # Authority depends on gate size relative to channel size
                authority = min(
                    gate.max_opening / (upstream_channel.sections[0].max_depth),
                    1.0
                )
            
            characteristics[gate.gate_id] = GateFlowCharacteristics(
                gate_id=gate.gate_id,
                discharge_coefficient=discharge_coeff,
                max_flow=min(max_flow, upstream_capacity, downstream_capacity),
                min_flow=0.1,  # Minimum controllable flow
                upstream_channel_capacity=upstream_capacity,
                downstream_channel_capacity=downstream_capacity,
                gate_authority=authority
            )
        
        return characteristics
    
    def _get_initial_guess(
        self,
        current_settings: Optional[Dict[str, float]],
        zone_requests: List[ZoneDeliveryRequest],
        total_inflow: float
    ) -> np.ndarray:
        """Generate initial guess for gate openings"""
        x0 = np.zeros(len(self.automated_gates))
        
        if current_settings:
            # Start from current settings
            for i, gate in enumerate(self.automated_gates):
                x0[i] = current_settings.get(gate.gate_id, 0.5)
        else:
            # Proportional distribution based on demands
            total_demand = sum(req.required_flow_rate for req in zone_requests)
            if total_demand > 0:
                # Distribute proportionally
                for i in range(len(self.automated_gates)):
                    x0[i] = 0.5 * min(total_inflow / total_demand, 1.0)
            else:
                x0.fill(0.5)  # Default to half open
        
        return x0
    
    def _build_constraints(
        self,
        total_inflow: float,
        zone_requests: List[ZoneDeliveryRequest]
    ) -> List:
        """Build optimization constraints"""
        constraints = []
        n_gates = len(self.automated_gates)
        
        # Flow conservation constraint
        def flow_balance(x):
            total_gate_flow = sum(
                self._calculate_gate_flow(self.automated_gates[i], x[i], total_inflow)
                for i in range(n_gates)
            )
            return total_inflow - total_gate_flow
        
        constraints.append({
            'type': 'eq',
            'fun': flow_balance
        })
        
        # Zone demand satisfaction constraints (with relaxation)
        for zone_req in zone_requests:
            def zone_constraint(x, zone_id=zone_req.zone_id, demand=zone_req.required_flow_rate):
                zone_flow = self._calculate_zone_flow_from_gates(x, zone_id)
                # Allow 20% deviation from demand
                return abs(zone_flow - demand) - 0.2 * demand
            
            constraints.append({
                'type': 'ineq',
                'fun': zone_constraint
            })
        
        # Gate capacity constraints
        for i, gate in enumerate(self.automated_gates):
            char = self.gate_characteristics[gate.gate_id]
            
            def capacity_constraint(x, idx=i, max_flow=char.max_flow):
                gate_flow = self._calculate_gate_flow(
                    self.automated_gates[idx], x[idx], total_inflow
                )
                return max_flow - gate_flow
            
            constraints.append({
                'type': 'ineq',
                'fun': capacity_constraint
            })
        
        # Smooth operation constraint (limit rapid changes)
        if len(self.automated_gates) > 1:
            def smoothness_constraint(x):
                # Penalize large differences between adjacent gates
                diffs = np.diff(x)
                return 0.5 - np.max(np.abs(diffs))
            
            constraints.append({
                'type': 'ineq',
                'fun': smoothness_constraint
            })
        
        return constraints
    
    def _calculate_gate_flow(self, gate: Gate, opening: float, upstream_flow: float) -> float:
        """Calculate flow through a gate given opening"""
        char = self.gate_characteristics[gate.gate_id]
        
        # Simplified gate flow equation
        # Q = Cd * a * sqrt(2 * g * h)
        # Assume head proportional to upstream flow
        effective_head = min(2.0, upstream_flow / 10.0)  # Simplified relationship
        
        gate_area = opening * gate.max_opening * 5.0  # Assume 5m width
        flow = char.discharge_coefficient * gate_area * np.sqrt(
            2 * settings.gravity * effective_head
        )
        
        # Apply constraints
        flow = min(flow, char.max_flow, upstream_flow)
        flow = max(flow, 0)
        
        return flow
    
    def _calculate_zone_flow_from_gates(self, gate_openings: np.ndarray, zone_id: str) -> float:
        """Calculate total flow reaching a zone from gate settings"""
        zone_flow = 0
        
        # Simplified: assume certain gates serve certain zones
        # In reality, this would use the network topology
        zone_gates = self._get_gates_for_zone(zone_id)
        
        for gate_id in zone_gates:
            gate_idx = next(
                i for i, g in enumerate(self.automated_gates) if g.gate_id == gate_id
            )
            gate = self.automated_gates[gate_idx]
            gate_flow = self._calculate_gate_flow(gate, gate_openings[gate_idx], 100.0)
            zone_flow += gate_flow * 0.9  # 90% efficiency
        
        return zone_flow
    
    def _get_gates_for_zone(self, zone_id: str) -> List[str]:
        """Get gates that deliver water to a specific zone"""
        # Simplified mapping - in reality would use network topology
        zone_gate_map = {
            "zone_1": ["gate_1", "gate_2", "gate_3"],
            "zone_2": ["gate_4", "gate_5", "gate_6"],
            "zone_3": ["gate_7", "gate_8", "gate_9"],
            "zone_4": ["gate_10", "gate_11", "gate_12"],
            "zone_5": ["gate_13", "gate_14", "gate_15"],
            "zone_6": ["gate_16", "gate_17", "gate_18", "gate_19", "gate_20"]
        }
        
        gates = zone_gate_map.get(zone_id, [])
        # Filter to only include automated gates that exist
        available_gate_ids = [g.gate_id for g in self.automated_gates]
        return [g for g in gates if g in available_gate_ids]
    
    def _objective_minimize_travel_time(
        self,
        gate_openings: np.ndarray,
        zone_requests: List[ZoneDeliveryRequest]
    ) -> float:
        """Objective: minimize water travel time to zones"""
        total_time = 0
        
        for zone_req in zone_requests:
            zone_flow = self._calculate_zone_flow_from_gates(gate_openings, zone_req.zone_id)
            if zone_flow > 0:
                # Travel time inversely proportional to flow velocity
                # Simplified: assume 10km average distance, velocity = flow/area
                avg_velocity = max(0.3, min(2.0, zone_flow / 10.0))
                travel_time = 10000 / (avg_velocity * 60)  # Time in minutes
                total_time += travel_time * zone_req.priority
        
        return total_time
    
    def _objective_maximize_efficiency(
        self,
        gate_openings: np.ndarray,
        zone_requests: List[ZoneDeliveryRequest]
    ) -> float:
        """Objective: maximize delivery efficiency"""
        total_delivered = 0
        total_demanded = 0
        
        for zone_req in zone_requests:
            zone_flow = self._calculate_zone_flow_from_gates(gate_openings, zone_req.zone_id)
            delivered = min(zone_flow, zone_req.required_flow_rate)
            total_delivered += delivered * zone_req.priority
            total_demanded += zone_req.required_flow_rate * zone_req.priority
        
        efficiency = total_delivered / max(total_demanded, 1e-6)
        return -efficiency  # Negative because we minimize
    
    def _objective_minimize_energy_loss(
        self,
        gate_openings: np.ndarray,
        zone_requests: List[ZoneDeliveryRequest]
    ) -> float:
        """Objective: minimize energy losses through gates"""
        total_loss = 0
        
        for i, gate in enumerate(self.automated_gates):
            opening = gate_openings[i]
            # Energy loss proportional to (1 - opening)² for partially open gates
            loss_factor = (1 - opening) ** 2 if opening < 0.95 else 0
            gate_flow = self._calculate_gate_flow(gate, opening, 100.0)
            energy_loss = loss_factor * gate_flow * settings.gravity * 0.5  # Simplified
            total_loss += energy_loss
        
        return total_loss
    
    def _objective_balanced(
        self,
        gate_openings: np.ndarray,
        zone_requests: List[ZoneDeliveryRequest]
    ) -> float:
        """Balanced objective combining multiple factors"""
        # Weighted combination of objectives
        time_weight = 0.3
        efficiency_weight = 0.5
        energy_weight = 0.2
        
        time_obj = self._objective_minimize_travel_time(gate_openings, zone_requests)
        eff_obj = self._objective_maximize_efficiency(gate_openings, zone_requests)
        energy_obj = self._objective_minimize_energy_loss(gate_openings, zone_requests)
        
        # Normalize objectives
        normalized_obj = (
            time_weight * time_obj / 1000 +  # Normalize time to ~1
            efficiency_weight * eff_obj +
            energy_weight * energy_obj / 100  # Normalize energy to ~1
        )
        
        return normalized_obj
    
    def _extract_gate_settings(
        self,
        gate_openings: np.ndarray,
        total_inflow: float
    ) -> List[GateSetting]:
        """Extract gate settings from optimization result"""
        settings_list = []
        
        for i, gate in enumerate(self.automated_gates):
            opening = gate_openings[i]
            flow = self._calculate_gate_flow(gate, opening, total_inflow)
            
            # Estimate heads (simplified)
            upstream_head = 2.0 * (flow / self.gate_characteristics[gate.gate_id].max_flow)
            downstream_head = upstream_head * 0.7  # Assume 30% head loss
            
            setting = GateSetting(
                gate_id=gate.gate_id,
                opening_ratio=opening,
                timestamp=datetime.now(),
                flow_rate=flow,
                upstream_head=upstream_head,
                downstream_head=downstream_head
            )
            settings_list.append(setting)
        
        return settings_list
    
    def _calculate_zone_flows(
        self,
        gate_settings: List[GateSetting],
        zone_requests: List[ZoneDeliveryRequest]
    ) -> Dict[str, float]:
        """Calculate actual flow to each zone from gate settings"""
        zone_flows = {}
        
        for zone_req in zone_requests:
            zone_gates = self._get_gates_for_zone(zone_req.zone_id)
            zone_flow = sum(
                gs.flow_rate * 0.9  # 90% delivery efficiency
                for gs in gate_settings
                if gs.gate_id in zone_gates
            )
            zone_flows[zone_req.zone_id] = zone_flow
        
        return zone_flows
    
    def _calculate_efficiency(
        self,
        zone_flows: Dict[str, float],
        zone_requests: List[ZoneDeliveryRequest],
        total_inflow: float
    ) -> float:
        """Calculate overall system efficiency"""
        total_delivered = sum(zone_flows.values())
        total_demanded = sum(req.required_flow_rate for req in zone_requests)
        
        # Efficiency based on demand satisfaction and flow utilization
        demand_satisfaction = min(total_delivered / max(total_demanded, 1e-6), 1.0)
        flow_utilization = total_delivered / max(total_inflow, 1e-6)
        
        return (demand_satisfaction + flow_utilization) / 2