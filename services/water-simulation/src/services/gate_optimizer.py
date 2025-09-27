"""
Gate optimization algorithms for water distribution
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from scipy.optimize import linprog, minimize
from dataclasses import dataclass
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class OptimizationConstraint:
    """Represents an optimization constraint"""
    constraint_type: str  # 'gate_capacity', 'water_level', 'delivery_window'
    resource_id: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    priority: int = 1  # Higher = more important
    

class GateOptimizer:
    """Optimizes gate operations for water distribution"""
    
    def __init__(
        self,
        network_topology: Dict[str, Any],
        gate_properties: Dict[str, Dict],
        section_details: Dict[str, Dict]
    ):
        self.topology = network_topology
        self.gates = gate_properties
        self.sections = section_details
        
        # Build mappings
        self._build_network_mappings()
        
    def _build_network_mappings(self) -> None:
        """Build useful network mappings"""
        self.gate_to_sections = {}
        self.section_to_gate = {}
        
        for section_id, section in self.sections.items():
            gate_id = section.get("delivery_gate")
            if gate_id:
                self.section_to_gate[section_id] = gate_id
                if gate_id not in self.gate_to_sections:
                    self.gate_to_sections[gate_id] = []
                self.gate_to_sections[gate_id].append(section_id)
    
    async def optimize(
        self,
        demands: Dict[str, float],
        current_state: Dict[str, Any],
        objective: str = "multi_objective",
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Main optimization entry point"""
        start_time = datetime.utcnow()
        
        try:
            if objective == "water_efficiency":
                result = await self._optimize_water_efficiency(
                    demands, current_state, constraints
                )
            elif objective == "fairness":
                result = await self._optimize_fairness(
                    demands, current_state, constraints
                )
            elif objective == "energy_minimal":
                result = await self._optimize_energy(
                    demands, current_state, constraints
                )
            else:  # multi_objective
                result = await self._optimize_multi_objective(
                    demands, current_state, constraints
                )
            
            # Add computation time
            computation_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            result["computation_time_ms"] = int(computation_time)
            
            return result
            
        except Exception as e:
            logger.error(f"Optimization failed: {str(e)}")
            # Return fallback solution
            return self._create_fallback_solution(demands, current_state)
    
    async def _optimize_water_efficiency(
        self,
        demands: Dict[str, float],
        current_state: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Optimize for maximum water delivery efficiency"""
        
        # Decision variables: gate openings
        gate_ids = list(self.gates.keys())
        n_gates = len(gate_ids)
        
        # Objective: maximize water delivery / water used
        # For linear programming, we minimize negative efficiency
        
        # Build constraint matrices
        A_ub = []  # Inequality constraints (Ax <= b)
        b_ub = []
        A_eq = []  # Equality constraints (Ax = b)
        b_eq = []
        bounds = []
        
        # Gate opening bounds
        for i, gate_id in enumerate(gate_ids):
            gate_props = self.gates[gate_id]
            max_opening = gate_props.get("max_opening_m", 2.0)
            
            # Check for discrete levels
            if "discrete_levels" in gate_props and gate_props["discrete_levels"]:
                # For now, use continuous approximation
                bounds.append((0, max_opening))
            else:
                bounds.append((0, max_opening))
        
        # Capacity constraints
        for i, gate_id in enumerate(gate_ids):
            # Gate flow capacity constraint
            capacity_constraint = np.zeros(n_gates)
            capacity_constraint[i] = 1
            
            # Estimate max flow based on typical conditions
            max_flow = self._estimate_gate_capacity(gate_id, current_state)
            
            A_ub.append(capacity_constraint)
            b_ub.append(max_flow)
        
        # Demand satisfaction constraints
        total_demand = sum(demands.values())
        
        # Simple objective: minimize total gate openings (proxy for water use)
        c = np.ones(n_gates)
        
        # Add delivery constraints
        for section_id, demand in demands.items():
            gate_id = self.section_to_gate.get(section_id)
            if gate_id and gate_id in gate_ids:
                gate_idx = gate_ids.index(gate_id)
                
                # Ensure gate can deliver required flow
                delivery_constraint = np.zeros(n_gates)
                delivery_constraint[gate_idx] = -1  # Negative because we need >= demand
                
                A_ub.append(delivery_constraint)
                b_ub.append(-demand * 0.001)  # Convert to approximate opening
        
        # Solve linear program
        if A_ub:
            result = linprog(
                c=c,
                A_ub=np.array(A_ub) if A_ub else None,
                b_ub=np.array(b_ub) if b_ub else None,
                A_eq=np.array(A_eq) if A_eq else None,
                b_eq=np.array(b_eq) if b_eq else None,
                bounds=bounds,
                method='highs'
            )
            
            if result.success:
                gate_schedule = {
                    gate_ids[i]: float(result.x[i])
                    for i in range(n_gates)
                }
                
                # Calculate allocations
                allocations = self._calculate_allocations(
                    gate_schedule, demands, current_state
                )
                
                # Calculate efficiency
                total_delivered = sum(allocations.values())
                total_requested = sum(demands.values())
                efficiency = total_delivered / total_requested if total_requested > 0 else 0
                
                return {
                    "gate_schedule": gate_schedule,
                    "allocations": allocations,
                    "efficiency_score": efficiency,
                    "fairness_index": self._calculate_fairness_index(allocations, demands),
                    "energy_usage": self._estimate_energy_usage(gate_schedule, current_state),
                    "iterations": result.nit,
                    "converged": True
                }
            else:
                logger.warning(f"Optimization failed: {result.message}")
        
        # Fallback to heuristic
        return self._heuristic_optimization(demands, current_state)
    
    async def _optimize_fairness(
        self,
        demands: Dict[str, float],
        current_state: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Optimize for fair water distribution (max-min fairness)"""
        
        # Use Jain's fairness index as objective
        # Maximize min(delivery_ratio) across all sections
        
        def fairness_objective(gate_openings):
            """Objective function for fairness (to minimize)"""
            gate_schedule = {
                gate_id: opening
                for gate_id, opening in zip(self.gates.keys(), gate_openings)
            }
            
            allocations = self._calculate_allocations(
                gate_schedule, demands, current_state
            )
            
            # Calculate delivery ratios
            ratios = []
            for section_id, demand in demands.items():
                if demand > 0:
                    delivered = allocations.get(section_id, 0)
                    ratio = delivered / demand
                    ratios.append(min(1.0, ratio))
            
            if not ratios:
                return 0
            
            # Negative Jain's fairness index (to minimize)
            sum_ratios = sum(ratios)
            sum_squared = sum(r**2 for r in ratios)
            n = len(ratios)
            
            if sum_squared > 0:
                fairness = (sum_ratios ** 2) / (n * sum_squared)
                return -fairness  # Negative because we minimize
            return 0
        
        # Initial guess and bounds
        x0 = np.ones(len(self.gates)) * 0.5
        bounds = [(0, gate.get("max_opening_m", 2.0)) for gate in self.gates.values()]
        
        # Optimize
        result = minimize(
            fairness_objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            options={'maxiter': 100}
        )
        
        if result.success:
            gate_schedule = {
                gate_id: float(opening)
                for gate_id, opening in zip(self.gates.keys(), result.x)
            }
            
            allocations = self._calculate_allocations(
                gate_schedule, demands, current_state
            )
            
            return {
                "gate_schedule": gate_schedule,
                "allocations": allocations,
                "efficiency_score": self._calculate_efficiency(allocations, demands),
                "fairness_index": -result.fun,  # Convert back to positive
                "energy_usage": self._estimate_energy_usage(gate_schedule, current_state),
                "iterations": result.nit,
                "converged": True
            }
        
        return self._heuristic_optimization(demands, current_state)
    
    async def _optimize_energy(
        self,
        demands: Dict[str, float],
        current_state: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Optimize for minimum energy consumption"""
        
        # Minimize gate movements and pumping energy
        current_positions = current_state.get("gate_positions", {})
        
        def energy_objective(gate_openings):
            """Energy consumption objective"""
            total_energy = 0
            
            for i, (gate_id, opening) in enumerate(zip(self.gates.keys(), gate_openings)):
                current_pos = current_positions.get(gate_id, 0)
                movement = abs(opening - current_pos)
                
                # Energy proportional to movement
                gate_props = self.gates[gate_id]
                gate_area = gate_props.get("width_m", 1) * gate_props.get("height_m", 1)
                
                # Simple energy model
                movement_energy = movement * gate_area * 10  # kWh
                total_energy += movement_energy
                
                # Add pumping energy if gate requires it
                if gate_props.get("requires_pumping", False):
                    flow = self._estimate_gate_flow(gate_id, opening, current_state)
                    pump_energy = flow * 0.1  # kWh per m³/s
                    total_energy += pump_energy
            
            # Penalize if demands not met
            gate_schedule = {
                gate_id: opening
                for gate_id, opening in zip(self.gates.keys(), gate_openings)
            }
            allocations = self._calculate_allocations(
                gate_schedule, demands, current_state
            )
            
            unmet_demand = sum(
                max(0, demand - allocations.get(sid, 0))
                for sid, demand in demands.items()
            )
            
            total_energy += unmet_demand * 1000  # Heavy penalty
            
            return total_energy
        
        # Optimize
        x0 = [current_positions.get(gid, 0.5) for gid in self.gates.keys()]
        bounds = [(0, gate.get("max_opening_m", 2.0)) for gate in self.gates.values()]
        
        result = minimize(
            energy_objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            options={'maxiter': 100}
        )
        
        if result.success:
            gate_schedule = {
                gate_id: float(opening)
                for gate_id, opening in zip(self.gates.keys(), result.x)
            }
            
            allocations = self._calculate_allocations(
                gate_schedule, demands, current_state
            )
            
            return {
                "gate_schedule": gate_schedule,
                "allocations": allocations,
                "efficiency_score": self._calculate_efficiency(allocations, demands),
                "fairness_index": self._calculate_fairness_index(allocations, demands),
                "energy_usage": result.fun,
                "iterations": result.nit,
                "converged": True
            }
        
        return self._heuristic_optimization(demands, current_state)
    
    async def _optimize_multi_objective(
        self,
        demands: Dict[str, float],
        current_state: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Multi-objective optimization combining efficiency, fairness, and energy"""
        
        # Weight factors
        w_efficiency = 0.4
        w_fairness = 0.4
        w_energy = 0.2
        
        current_positions = current_state.get("gate_positions", {})
        
        def multi_objective(gate_openings):
            """Combined objective function"""
            gate_schedule = {
                gate_id: opening
                for gate_id, opening in zip(self.gates.keys(), gate_openings)
            }
            
            allocations = self._calculate_allocations(
                gate_schedule, demands, current_state
            )
            
            # Efficiency score (0-1, higher is better)
            efficiency = self._calculate_efficiency(allocations, demands)
            
            # Fairness score (0-1, higher is better)
            fairness = self._calculate_fairness_index(allocations, demands)
            
            # Energy score (normalized, lower is better)
            energy = 0
            for gate_id, opening in gate_schedule.items():
                current_pos = current_positions.get(gate_id, 0)
                movement = abs(opening - current_pos)
                energy += movement
            
            energy_normalized = energy / (len(self.gates) * 2.0)  # Normalize to 0-1
            
            # Combined score (to minimize)
            score = -w_efficiency * efficiency - w_fairness * fairness + w_energy * energy_normalized
            
            # Add penalty for unmet demands
            total_demand = sum(demands.values())
            total_delivered = sum(allocations.values())
            if total_delivered < total_demand * 0.9:
                score += 10  # Large penalty
            
            return score
        
        # Optimize
        x0 = [current_positions.get(gid, 0.5) for gid in self.gates.keys()]
        bounds = [(0, gate.get("max_opening_m", 2.0)) for gate in self.gates.values()]
        
        result = minimize(
            multi_objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            options={'maxiter': 200}
        )
        
        if result.success:
            gate_schedule = {
                gate_id: float(opening)
                for gate_id, opening in zip(self.gates.keys(), result.x)
            }
            
            allocations = self._calculate_allocations(
                gate_schedule, demands, current_state
            )
            
            return {
                "gate_schedule": gate_schedule,
                "allocations": allocations,
                "efficiency_score": self._calculate_efficiency(allocations, demands),
                "fairness_index": self._calculate_fairness_index(allocations, demands),
                "energy_usage": self._estimate_energy_usage(gate_schedule, current_state),
                "iterations": result.nit,
                "converged": True,
                "objective_value": -result.fun
            }
        
        return self._heuristic_optimization(demands, current_state)
    
    def _heuristic_optimization(
        self,
        demands: Dict[str, float],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fallback heuristic optimization"""
        gate_schedule = {}
        
        # Simple proportional opening based on demand
        for gate_id, section_ids in self.gate_to_sections.items():
            total_gate_demand = sum(
                demands.get(sid, 0) for sid in section_ids
            )
            
            # Estimate required opening
            gate_props = self.gates[gate_id]
            max_opening = gate_props.get("max_opening_m", 2.0)
            
            # Simple linear relationship
            if total_gate_demand > 0:
                estimated_opening = min(
                    max_opening,
                    total_gate_demand * 0.001  # Rough conversion
                )
            else:
                estimated_opening = 0
            
            gate_schedule[gate_id] = estimated_opening
        
        allocations = self._calculate_allocations(
            gate_schedule, demands, current_state
        )
        
        return {
            "gate_schedule": gate_schedule,
            "allocations": allocations,
            "efficiency_score": self._calculate_efficiency(allocations, demands),
            "fairness_index": self._calculate_fairness_index(allocations, demands),
            "energy_usage": self._estimate_energy_usage(gate_schedule, current_state),
            "iterations": 0,
            "converged": False
        }
    
    def _calculate_allocations(
        self,
        gate_schedule: Dict[str, float],
        demands: Dict[str, float],
        current_state: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate water allocations based on gate schedule"""
        allocations = {}
        
        for section_id, demand in demands.items():
            gate_id = self.section_to_gate.get(section_id)
            
            if gate_id and gate_id in gate_schedule:
                gate_opening = gate_schedule[gate_id]
                
                # Estimate flow through gate
                flow = self._estimate_gate_flow(gate_id, gate_opening, current_state)
                
                # Distribute flow among sections served by gate
                sections_at_gate = self.gate_to_sections.get(gate_id, [])
                if sections_at_gate:
                    # Proportional distribution based on demand
                    total_demand_at_gate = sum(
                        demands.get(s, 0) for s in sections_at_gate
                    )
                    
                    if total_demand_at_gate > 0:
                        section_share = demand / total_demand_at_gate
                        allocations[section_id] = flow * section_share
                    else:
                        allocations[section_id] = 0
                else:
                    allocations[section_id] = 0
            else:
                allocations[section_id] = 0
        
        return allocations
    
    def _estimate_gate_flow(
        self,
        gate_id: str,
        opening: float,
        current_state: Dict[str, Any]
    ) -> float:
        """Estimate flow through gate"""
        # Simple flow model
        gate_props = self.gates[gate_id]
        
        # Get water levels
        water_levels = current_state.get("water_levels", {})
        upstream_level = water_levels.get(f"{gate_id}_upstream", 3.0)
        downstream_level = water_levels.get(f"{gate_id}_downstream", 2.0)
        
        head_diff = max(0, upstream_level - downstream_level)
        
        # Orifice equation approximation
        Cd = 0.6  # Discharge coefficient
        g = 9.81
        
        if gate_props.get("shape") == "circular":
            area = np.pi * (gate_props.get("diameter_m", 1) / 2) ** 2
        else:
            area = gate_props.get("width_m", 1) * opening
        
        flow = Cd * area * np.sqrt(2 * g * head_diff)
        
        return flow
    
    def _estimate_gate_capacity(
        self,
        gate_id: str,
        current_state: Dict[str, Any]
    ) -> float:
        """Estimate maximum flow capacity of gate"""
        gate_props = self.gates[gate_id]
        max_opening = gate_props.get("max_opening_m", 2.0)
        
        return self._estimate_gate_flow(gate_id, max_opening, current_state)
    
    def _calculate_efficiency(
        self,
        allocations: Dict[str, float],
        demands: Dict[str, float]
    ) -> float:
        """Calculate water delivery efficiency"""
        total_delivered = sum(allocations.values())
        total_requested = sum(demands.values())
        
        if total_requested > 0:
            return min(1.0, total_delivered / total_requested)
        return 0
    
    def _calculate_fairness_index(
        self,
        allocations: Dict[str, float],
        demands: Dict[str, float]
    ) -> float:
        """Calculate Jain's fairness index"""
        ratios = []
        
        for section_id, demand in demands.items():
            if demand > 0:
                delivered = allocations.get(section_id, 0)
                ratio = min(1.0, delivered / demand)
                ratios.append(ratio)
        
        if not ratios:
            return 0
        
        n = len(ratios)
        sum_ratios = sum(ratios)
        sum_squared = sum(r**2 for r in ratios)
        
        if sum_squared > 0:
            return (sum_ratios ** 2) / (n * sum_squared)
        return 0
    
    def _estimate_energy_usage(
        self,
        gate_schedule: Dict[str, float],
        current_state: Dict[str, Any]
    ) -> float:
        """Estimate total energy usage"""
        total_energy = 0
        current_positions = current_state.get("gate_positions", {})
        
        for gate_id, target_opening in gate_schedule.items():
            current_pos = current_positions.get(gate_id, 0)
            movement = abs(target_opening - current_pos)
            
            gate_props = self.gates[gate_id]
            
            # Movement energy
            gate_area = gate_props.get("width_m", 1) * gate_props.get("height_m", 1)
            movement_energy = movement * gate_area * 5  # kWh
            
            total_energy += movement_energy
        
        return total_energy
    
    def _create_fallback_solution(
        self,
        demands: Dict[str, float],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create fallback solution when optimization fails"""
        # Keep current gate positions
        current_positions = current_state.get("gate_positions", {})
        
        allocations = self._calculate_allocations(
            current_positions, demands, current_state
        )
        
        return {
            "gate_schedule": current_positions,
            "allocations": allocations,
            "efficiency_score": self._calculate_efficiency(allocations, demands),
            "fairness_index": self._calculate_fairness_index(allocations, demands),
            "energy_usage": 0,  # No movement
            "iterations": 0,
            "converged": False,
            "error": "Optimization failed, using current positions"
        }