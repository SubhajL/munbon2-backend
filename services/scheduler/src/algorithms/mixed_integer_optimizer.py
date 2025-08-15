from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import pulp
import numpy as np
from collections import defaultdict

from ..core.logger import get_logger
from .constraint_builder import ConstraintBuilder
from .travel_optimizer import TravelOptimizer

logger = get_logger(__name__)


class MixedIntegerOptimizer:
    """Mixed Integer Linear Programming optimizer for irrigation scheduling"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.solver_timeout = config.get("timeout_seconds", 60)
        self.travel_optimizer = TravelOptimizer()
        
    def optimize(
        self,
        demands: Dict[str, Any],
        network: Dict[str, Any],
        teams: List[Dict],
        constraints: List[Any],
        time_horizon: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run the optimization to generate schedule"""
        logger.info("Starting MILP optimization")
        
        # Prepare data
        time_slots = self._generate_time_slots(time_horizon)
        operation_days = time_horizon.get("operation_days", [1, 3])  # Tuesday, Thursday
        
        # Build constraints
        constraint_builder = ConstraintBuilder(network, teams, constraints)
        all_constraints = constraint_builder.build_all_constraints(
            demands, time_slots, operation_days
        )
        
        # Create optimization model
        model = self._create_model(
            demands, network, teams, time_slots, operation_days, all_constraints
        )
        
        # Solve
        solution = self._solve_model(model, time_slots)
        
        # Post-process solution
        schedule = self._extract_schedule(solution, network, teams, time_slots)
        
        return schedule
    
    def _generate_time_slots(self, time_horizon: Dict) -> List[datetime]:
        """Generate discrete time slots for the planning horizon"""
        start_date = time_horizon["start_date"]
        end_date = time_horizon["end_date"]
        slot_duration = timedelta(minutes=time_horizon.get("slot_minutes", 30))
        
        time_slots = []
        current = datetime.combine(start_date, datetime.min.time())
        end = datetime.combine(end_date, datetime.max.time())
        
        while current <= end:
            # Only include working hours
            if 6 <= current.hour <= 18:
                time_slots.append(current)
            current += slot_duration
        
        return time_slots
    
    def _create_model(
        self,
        demands: Dict,
        network: Dict,
        teams: List,
        time_slots: List,
        operation_days: List,
        constraints: Dict
    ) -> pulp.LpProblem:
        """Create the MILP model"""
        
        # Initialize model
        model = pulp.LpProblem("IrrigationSchedule", pulp.LpMinimize)
        
        # Extract data
        gates = list(network.get("gates", {}).keys())
        team_ids = [t["team_code"] for t in teams]
        T = len(time_slots)
        
        # Decision Variables
        
        # 1. Gate opening percentage (0-100)
        gate_opening = {}
        for g in gates:
            for t in range(T):
                gate_opening[g, t] = pulp.LpVariable(
                    f"opening_{g}_{t}", 0, 100, pulp.LpContinuous
                )
        
        # 2. Gate flow rate (m³/s)
        gate_flow = {}
        for g in gates:
            for t in range(T):
                max_flow = network["gates"][g].get("q_max", 10.0)
                gate_flow[g, t] = pulp.LpVariable(
                    f"flow_{g}_{t}", 0, max_flow, pulp.LpContinuous
                )
        
        # 3. Binary: gate operation occurs
        gate_operated = {}
        for g in gates:
            for t in range(T):
                gate_operated[g, t] = pulp.LpVariable(
                    f"operated_{g}_{t}", cat=pulp.LpBinary
                )
        
        # 4. Binary: team assignment
        team_assignment = {}
        for team in team_ids:
            for g in gates:
                for t in range(T):
                    team_assignment[team, g, t] = pulp.LpVariable(
                        f"assign_{team}_{g}_{t}", cat=pulp.LpBinary
                    )
        
        # 5. Binary: routing between gates
        routing = {}
        for team in team_ids:
            for g1 in gates:
                for g2 in gates:
                    if g1 != g2:
                        for d in operation_days:
                            routing[team, g1, g2, d] = pulp.LpVariable(
                                f"route_{team}_{g1}_{g2}_d{d}", cat=pulp.LpBinary
                            )
        
        # 6. Water spillage (excess flow)
        spillage = {}
        for zone in demands.get("byZone", {}).keys():
            for t in range(T):
                spillage[zone, t] = pulp.LpVariable(
                    f"spill_{zone}_{t}", 0, None, pulp.LpContinuous
                )
        
        # Objective Function
        obj = self._build_objective(
            gate_operated, routing, spillage, network, teams, time_slots
        )
        model += obj
        
        # Add Constraints
        self._add_constraints_to_model(
            model, constraints, gate_opening, gate_flow, gate_operated,
            team_assignment, routing, spillage, gates, team_ids, time_slots
        )
        
        return model
    
    def _build_objective(
        self,
        gate_operated: Dict,
        routing: Dict,
        spillage: Dict,
        network: Dict,
        teams: List,
        time_slots: List
    ) -> pulp.LpAffineExpression:
        """Build objective function"""
        
        # Weights for different objectives
        w_travel = 1.0      # Weight for travel distance
        w_changes = 10.0    # Weight for gate changes
        w_spillage = 100.0  # Weight for water spillage
        
        obj = 0
        
        # 1. Minimize travel distance
        for key, var in routing.items():
            team, g1, g2, day = key
            distance = self._calculate_distance(
                network["gates"][g1], network["gates"][g2]
            )
            obj += w_travel * distance * var
        
        # 2. Minimize gate changes
        for key, var in gate_operated.items():
            obj += w_changes * var
        
        # 3. Minimize water spillage
        for key, var in spillage.items():
            obj += w_spillage * var
        
        return obj
    
    def _calculate_distance(self, gate1: Dict, gate2: Dict) -> float:
        """Calculate distance between two gates in km"""
        # Simplified distance calculation
        # In reality, would use road network distance
        lat1, lon1 = gate1.get("latitude", 0), gate1.get("longitude", 0)
        lat2, lon2 = gate2.get("latitude", 0), gate2.get("longitude", 0)
        
        # Haversine formula (simplified)
        distance = np.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2) * 111  # km
        return distance
    
    def _add_constraints_to_model(
        self,
        model: pulp.LpProblem,
        constraints: Dict,
        gate_opening: Dict,
        gate_flow: Dict,
        gate_operated: Dict,
        team_assignment: Dict,
        routing: Dict,
        spillage: Dict,
        gates: List,
        teams: List,
        time_slots: List
    ):
        """Add all constraints to the model"""
        
        # Process each constraint type
        for constraint_type, constraint_list in constraints.items():
            for constraint in constraint_list:
                expr = 0
                
                # Build expression from variables
                for var_name, coeff in constraint["expression"]["variables"]:
                    # Parse variable name to get actual variable
                    var = self._get_variable_by_name(
                        var_name, gate_opening, gate_flow, gate_operated,
                        team_assignment, routing, spillage
                    )
                    if var is not None:
                        expr += coeff * var
                
                # Add constraint to model
                sense = constraint["expression"]["sense"]
                rhs = constraint["expression"]["rhs"]
                
                if sense == "<=":
                    model += expr <= rhs, constraint["name"]
                elif sense == ">=":
                    model += expr >= rhs, constraint["name"]
                elif sense == "=":
                    model += expr == rhs, constraint["name"]
        
        # Add additional logical constraints
        self._add_logical_constraints(
            model, gate_operated, team_assignment, gates, teams, time_slots
        )
    
    def _get_variable_by_name(self, var_name: str, *variable_dicts) -> Optional[pulp.LpVariable]:
        """Get variable by parsing its name"""
        # This is a simplified parser - in reality would be more robust
        parts = var_name.split("_")
        
        if parts[0] == "flow":
            gate, time = parts[1], int(parts[2])
            return variable_dicts[1].get((gate, time))
        elif parts[0] == "opening":
            gate, time = parts[1], int(parts[2])
            return variable_dicts[0].get((gate, time))
        elif parts[0] == "operated":
            gate, time = parts[1], int(parts[2])
            return variable_dicts[2].get((gate, time))
        
        return None
    
    def _add_logical_constraints(
        self,
        model: pulp.LpProblem,
        gate_operated: Dict,
        team_assignment: Dict,
        gates: List,
        teams: List,
        time_slots: List
    ):
        """Add logical constraints that link variables"""
        
        # If gate is operated, it must be assigned to exactly one team
        for g in gates:
            for t in range(len(time_slots)):
                model += (
                    pulp.lpSum(team_assignment[team, g, t] for team in teams) ==
                    gate_operated[g, t],
                    f"gate_team_link_{g}_{t}"
                )
    
    def _solve_model(self, model: pulp.LpProblem, time_slots: List) -> Dict[str, Any]:
        """Solve the optimization model"""
        logger.info(f"Solving model with {len(model.variables())} variables and {len(model.constraints)} constraints")
        
        # Choose solver
        solver = pulp.PULP_CBC_CMD(
            timeLimit=self.solver_timeout,
            msg=True,
            gapRel=0.05  # 5% optimality gap
        )
        
        # Solve
        model.solve(solver)
        
        # Extract solution
        status = pulp.LpStatus[model.status]
        logger.info(f"Optimization status: {status}")
        
        solution = {
            "status": status,
            "objective_value": pulp.value(model.objective),
            "variables": {},
            "solve_time": model.solutionTime,
        }
        
        # Extract variable values
        for var in model.variables():
            if var.varValue is not None and var.varValue > 0.001:
                solution["variables"][var.name] = var.varValue
        
        return solution
    
    def _extract_schedule(
        self,
        solution: Dict,
        network: Dict,
        teams: List,
        time_slots: List
    ) -> Dict[str, Any]:
        """Extract schedule from optimization solution"""
        
        operations = []
        team_routes = defaultdict(list)
        
        # Parse solution variables
        for var_name, value in solution["variables"].items():
            if var_name.startswith("assign_") and value > 0.5:
                # Team assignment
                parts = var_name.split("_")
                team_id = parts[1]
                gate_id = parts[2]
                time_idx = int(parts[3])
                
                operation = {
                    "gate_id": gate_id,
                    "team_id": team_id,
                    "time_slot": time_slots[time_idx],
                    "type": "manual",
                }
                
                # Get opening value
                opening_var = f"opening_{gate_id}_{time_idx}"
                flow_var = f"flow_{gate_id}_{time_idx}"
                
                operation["target_opening"] = solution["variables"].get(opening_var, 0)
                operation["expected_flow"] = solution["variables"].get(flow_var, 0)
                
                operations.append(operation)
                team_routes[team_id].append(operation)
        
        # Calculate metrics
        total_distance = 0
        for var_name, value in solution["variables"].items():
            if var_name.startswith("route_") and value > 0.5:
                parts = var_name.split("_")
                g1, g2 = parts[2], parts[3]
                distance = self._calculate_distance(
                    network["gates"][g1],
                    network["gates"][g2]
                )
                total_distance += distance
        
        schedule = {
            "status": solution["status"],
            "operations": operations,
            "team_routes": dict(team_routes),
            "metrics": {
                "total_operations": len(operations),
                "total_distance_km": total_distance,
                "optimization_time": solution["solve_time"],
                "objective_value": solution["objective_value"],
            }
        }
        
        return schedule