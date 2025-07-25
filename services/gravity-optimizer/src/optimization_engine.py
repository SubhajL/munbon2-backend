"""
Optimization engine for gravity flow
Uses linear programming and gradient-based methods to optimize gate settings
"""

import numpy as np
from scipy.optimize import minimize, LinearConstraint
from typing import List, Dict, Optional, Tuple
import logging
import time
from models import (
    TargetDelivery, GateState, OptimalGateSetting,
    OptimizationResult, OptimizationConstraints
)
from feasibility_checker import FeasibilityResults
from hydraulic_engine import HydraulicEngine

logger = logging.getLogger(__name__)

class OptimizationEngine:
    def __init__(self):
        self.hydraulic_engine = HydraulicEngine()
        self.active_optimizations = 0
        self.completed_today = 0
        self.total_computation_time = 0
        self.cache_hits = 0
        self.cache_requests = 0
    
    async def optimize_flow(
        self,
        target_deliveries: List[TargetDelivery],
        current_gate_states: Dict[str, GateState],
        feasibility_results: FeasibilityResults,
        constraints: OptimizationConstraints
    ) -> OptimizationResult:
        """Main optimization routine for gravity flow"""
        
        start_time = time.time()
        self.active_optimizations += 1
        
        try:
            # Extract feasible deliveries only
            feasible_deliveries = [
                d for d in target_deliveries 
                if d.section_id not in feasibility_results.infeasible_sections
            ]
            
            if not feasible_deliveries:
                logger.warning("No feasible deliveries to optimize")
                return self._create_empty_result()
            
            # Set up optimization problem
            gate_ids = list(current_gate_states.keys())
            n_gates = len(gate_ids)
            
            # Initial guess - current gate openings
            x0 = np.array([current_gate_states[gid].current_opening_m for gid in gate_ids])
            
            # Bounds - gate opening limits
            bounds = [(0, current_gate_states[gid].max_opening_m) for gid in gate_ids]
            
            # Objective function
            def objective(x):
                return self._calculate_objective(x, gate_ids, feasible_deliveries, current_gate_states)
            
            # Constraints
            constraints_list = self._build_constraints(
                gate_ids,
                feasible_deliveries,
                current_gate_states,
                constraints
            )
            
            # Optimize
            result = minimize(
                objective,
                x0,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints_list,
                options={
                    'maxiter': constraints.max_iterations,
                    'ftol': constraints.convergence_tolerance
                }
            )
            
            # Process results
            optimal_settings = await self._process_optimization_result(
                result.x,
                gate_ids,
                current_gate_states,
                feasible_deliveries
            )
            
            # Calculate delivery times
            delivery_times = await self._calculate_delivery_times(
                optimal_settings,
                feasible_deliveries
            )
            
            # Calculate total head loss
            total_head_loss = sum(s.head_loss_m for s in optimal_settings.values())
            
            computation_time = int((time.time() - start_time) * 1000)
            self.total_computation_time += computation_time
            self.completed_today += 1
            
            return OptimizationResult(
                gate_settings=optimal_settings,
                total_head_loss=total_head_loss,
                delivery_times=delivery_times,
                iterations=result.nit,
                convergence_error=result.fun,
                computation_time_ms=computation_time
            )
            
        finally:
            self.active_optimizations -= 1
    
    def _calculate_objective(
        self,
        x: np.ndarray,
        gate_ids: List[str],
        deliveries: List[TargetDelivery],
        gate_states: Dict[str, GateState]
    ) -> float:
        """
        Objective function to minimize:
        - Total head losses
        - Deviation from target flows
        - Gate movement from current position
        """
        
        total_loss = 0.0
        
        # Head loss term
        for i, gate_id in enumerate(gate_ids):
            opening = x[i]
            gate = gate_states[gate_id]
            
            # Estimate head loss (simplified)
            velocity = self._estimate_velocity(opening, gate.width_m)
            head_loss = 0.5 * velocity**2 / (2 * 9.81)  # Minor loss coefficient
            total_loss += head_loss
        
        # Flow deviation term
        for delivery in deliveries:
            # Estimate delivered flow (simplified)
            delivered_flow = self._estimate_delivered_flow(x, gate_ids, delivery)
            flow_deviation = abs(delivered_flow - delivery.required_flow_m3s)
            
            # Weight by priority
            priority_weight = {
                "critical": 10.0,
                "high": 5.0,
                "medium": 2.0,
                "low": 1.0
            }.get(delivery.priority.value, 1.0)
            
            total_loss += priority_weight * flow_deviation
        
        # Gate movement penalty (minimize adjustments)
        for i, gate_id in enumerate(gate_ids):
            current_opening = gate_states[gate_id].current_opening_m
            movement = abs(x[i] - current_opening)
            total_loss += 0.1 * movement  # Small penalty for movement
        
        return total_loss
    
    def _build_constraints(
        self,
        gate_ids: List[str],
        deliveries: List[TargetDelivery],
        gate_states: Dict[str, GateState],
        constraints: OptimizationConstraints
    ) -> List:
        """Build optimization constraints"""
        
        constraints_list = []
        
        # Flow conservation constraints
        # Sum of outflows <= inflow at each node
        node_flows = self._build_node_flow_matrix(gate_ids)
        
        if node_flows is not None:
            flow_constraint = LinearConstraint(
                node_flows,
                -np.inf,
                np.zeros(node_flows.shape[0])
            )
            constraints_list.append(flow_constraint)
        
        # Minimum depth constraints
        def depth_constraint(x):
            depths = []
            for i, gate_id in enumerate(gate_ids):
                # Estimate depth based on opening
                depth = self._estimate_depth(x[i], gate_states[gate_id])
                depths.append(depth - constraints.min_depth_m)
            return np.array(depths)
        
        constraints_list.append({
            'type': 'ineq',
            'fun': depth_constraint
        })
        
        # Velocity constraints
        def velocity_constraint(x):
            velocities = []
            for i, gate_id in enumerate(gate_ids):
                velocity = self._estimate_velocity(x[i], gate_states[gate_id].width_m)
                # Both min and max velocity
                velocities.append(velocity - constraints.min_velocity_ms)
                velocities.append(constraints.max_velocity_ms - velocity)
            return np.array(velocities)
        
        constraints_list.append({
            'type': 'ineq',
            'fun': velocity_constraint
        })
        
        return constraints_list
    
    def _build_node_flow_matrix(self, gate_ids: List[str]) -> Optional[np.ndarray]:
        """Build node-flow incidence matrix for flow conservation"""
        
        # Extract unique nodes
        nodes = set()
        for gate_id in gate_ids:
            parts = gate_id.split("->")
            if len(parts) == 2:
                nodes.add(parts[0])
                nodes.add(parts[1])
        
        if not nodes:
            return None
        
        nodes = sorted(list(nodes))
        n_nodes = len(nodes)
        n_gates = len(gate_ids)
        
        # Build incidence matrix
        matrix = np.zeros((n_nodes, n_gates))
        
        for j, gate_id in enumerate(gate_ids):
            parts = gate_id.split("->")
            if len(parts) == 2:
                upstream = parts[0]
                downstream = parts[1]
                
                if upstream in nodes:
                    i = nodes.index(upstream)
                    matrix[i, j] = -1  # Outflow
                
                if downstream in nodes:
                    i = nodes.index(downstream)
                    matrix[i, j] = 1   # Inflow
        
        return matrix
    
    async def _process_optimization_result(
        self,
        x: np.ndarray,
        gate_ids: List[str],
        gate_states: Dict[str, GateState],
        deliveries: List[TargetDelivery]
    ) -> Dict[str, OptimalGateSetting]:
        """Process optimization result into gate settings"""
        
        settings = {}
        
        for i, gate_id in enumerate(gate_ids):
            opening = x[i]
            gate = gate_states[gate_id]
            
            # Calculate flow through gate
            # Simplified - would use full hydraulic calculation
            flow = self._calculate_gate_flow(opening, gate)
            
            # Estimate water levels
            upstream_level = self._estimate_upstream_level(gate_id)
            downstream_level = upstream_level - 0.5  # Simplified
            
            # Calculate velocity and Froude number
            velocity = flow / (gate.width_m * opening) if opening > 0 else 0
            froude = velocity / np.sqrt(9.81 * opening) if opening > 0 else 0
            
            # Head loss
            head_loss = 0.1 * velocity**2 / (2 * 9.81) if velocity > 0 else 0
            
            settings[gate_id] = OptimalGateSetting(
                gate_id=gate_id,
                optimal_opening_m=opening,
                flow_m3s=flow,
                head_loss_m=head_loss,
                upstream_level_m=upstream_level,
                downstream_level_m=downstream_level,
                velocity_ms=velocity,
                froude_number=froude
            )
        
        return settings
    
    async def _calculate_delivery_times(
        self,
        gate_settings: Dict[str, OptimalGateSetting],
        deliveries: List[TargetDelivery]
    ) -> Dict[str, float]:
        """Calculate expected delivery times"""
        
        times = {}
        
        for delivery in deliveries:
            # Get path to delivery point
            path = self._get_delivery_path(delivery)
            
            # Calculate travel time along path
            travel_time = 0.0
            for i in range(len(path) - 1):
                canal_id = f"{path[i]}->{path[i+1]}"
                
                # Get velocity from gate settings
                if canal_id in gate_settings:
                    velocity = gate_settings[canal_id].velocity_ms
                else:
                    velocity = 1.0  # Default
                
                # Estimate canal length (would use actual data)
                length = 1000  # meters
                
                # Time = distance / velocity
                segment_time = length / velocity / 3600  # hours
                travel_time += segment_time
            
            times[delivery.section_id] = travel_time
        
        return times
    
    def _estimate_velocity(self, opening: float, width: float) -> float:
        """Estimate flow velocity"""
        if opening <= 0:
            return 0.0
        
        # Simple velocity estimate
        area = opening * width
        flow = area * 1.5  # Assume moderate flow
        velocity = flow / area
        return min(velocity, 2.0)  # Cap at max velocity
    
    def _estimate_depth(self, opening: float, gate: GateState) -> float:
        """Estimate water depth based on gate opening"""
        # Simplified - assumes depth slightly higher than opening
        return opening * 1.2
    
    def _estimate_delivered_flow(
        self,
        x: np.ndarray,
        gate_ids: List[str],
        delivery: TargetDelivery
    ) -> float:
        """Estimate flow delivered to a section"""
        
        # Find gate feeding this delivery
        zone_gate = f"M(0,{delivery.zone-1})->Zone_{delivery.zone}"
        
        if zone_gate in gate_ids:
            idx = gate_ids.index(zone_gate)
            opening = x[idx]
            # Simple flow calculation
            return opening * 2.5  # m³/s per meter opening
        
        return 0.0
    
    def _calculate_gate_flow(self, opening: float, gate: GateState) -> float:
        """Calculate flow through gate"""
        if opening <= 0:
            return 0.0
        
        # Simplified gate equation
        # Q = Cd * A * sqrt(2gh)
        cd = gate.calibration_k1
        area = opening * gate.width_m
        head = 0.5  # Assumed head difference
        
        flow = cd * area * np.sqrt(2 * 9.81 * head)
        return flow
    
    def _estimate_upstream_level(self, gate_id: str) -> float:
        """Estimate upstream water level"""
        # Node elevations plus typical depths
        levels = {
            "Source": 221.5,
            "M(0,0)": 219.2,
            "M(0,2)": 218.9,
            "M(0,5)": 218.8
        }
        
        upstream_node = gate_id.split("->")[0]
        return levels.get(upstream_node, 220.0)
    
    def _get_delivery_path(self, delivery: TargetDelivery) -> List[str]:
        """Get path to delivery point"""
        # Simplified path lookup
        paths = {
            1: ["Source", "M(0,0)", "M(0,1)", "Zone_1"],
            2: ["Source", "M(0,0)", "M(0,2)", "Zone_2"],
            3: ["Source", "M(0,0)", "M(0,3)", "Zone_3"],
            4: ["Source", "M(0,0)", "M(0,4)", "Zone_4"],
            5: ["Source", "M(0,0)", "M(0,5)", "Zone_5"],
            6: ["Source", "M(0,0)", "M(0,6)", "Zone_6"]
        }
        return paths.get(delivery.zone, [])
    
    def _create_empty_result(self) -> OptimizationResult:
        """Create empty optimization result"""
        return OptimizationResult(
            gate_settings={},
            total_head_loss=0.0,
            delivery_times={},
            iterations=0,
            convergence_error=0.0,
            computation_time_ms=0
        )
    
    def get_active_count(self) -> int:
        """Get number of active optimizations"""
        return self.active_optimizations
    
    def get_daily_stats(self) -> int:
        """Get number of optimizations completed today"""
        return self.completed_today
    
    def get_avg_computation_time(self) -> float:
        """Get average computation time in ms"""
        if self.completed_today > 0:
            return self.total_computation_time / self.completed_today
        return 0.0
    
    def get_cache_hit_rate(self) -> float:
        """Get cache hit rate"""
        if self.cache_requests > 0:
            return self.cache_hits / self.cache_requests
        return 0.0