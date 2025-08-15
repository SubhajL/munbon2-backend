from typing import Dict, List, Any, Tuple
from datetime import datetime, time, timedelta
import numpy as np

from ..core.logger import get_logger
from ..models.schedule import OptimizationConstraint

logger = get_logger(__name__)


class ConstraintBuilder:
    """Build constraints for the optimization model"""
    
    def __init__(self, network_data: Dict[str, Any], team_data: List[Dict], constraints: List[OptimizationConstraint]):
        self.network = network_data
        self.teams = team_data
        self.constraints = constraints
        self.gates = self._extract_gates()
        self.canals = self._extract_canals()
        
    def _extract_gates(self) -> Dict[str, Any]:
        """Extract gate information from network data"""
        gates = {}
        for gate_id, gate_data in self.network.get("gates", {}).items():
            gates[gate_id] = {
                "id": gate_id,
                "canal": gate_data.get("canal"),
                "zone": gate_data.get("zone"),
                "maxFlow": gate_data.get("q_max", 10.0),
                "area": gate_data.get("area", 0.0),
                "latitude": gate_data.get("latitude"),
                "longitude": gate_data.get("longitude"),
                "upstream": gate_data.get("upstream_gates", []),
                "downstream": gate_data.get("downstream_gates", []),
            }
        return gates
    
    def _extract_canals(self) -> Dict[str, Any]:
        """Extract canal information from network data"""
        canals = {}
        for canal_id, canal_data in self.network.get("canals", {}).items():
            canals[canal_id] = {
                "id": canal_id,
                "capacity": canal_data.get("capacity", 10.0),
                "length": canal_data.get("length", 1000.0),
                "manning_n": canal_data.get("manning_n", 0.025),
                "slope": canal_data.get("slope", 0.0001),
                "width": canal_data.get("width", 5.0),
            }
        return canals
    
    def build_demand_constraints(self, demands: Dict[str, Dict[str, float]], time_slots: List[datetime]) -> List[Dict]:
        """Build constraints for demand satisfaction"""
        constraints = []
        
        for zone_id, zone_demand in demands.items():
            for t, time_slot in enumerate(time_slots):
                # Find gates that deliver to this zone
                delivery_gates = [g for g, data in self.gates.items() if data["zone"] == zone_id]
                
                if delivery_gates:
                    constraint = {
                        "name": f"demand_satisfaction_{zone_id}_t{t}",
                        "type": "demand",
                        "expression": {
                            "variables": [(f"flow_{g}_{t}", 1.0) for g in delivery_gates],
                            "sense": ">=",
                            "rhs": zone_demand.get(f"hour_{t}", 0.0) / 3600  # Convert m³/h to m³/s
                        }
                    }
                    constraints.append(constraint)
        
        return constraints
    
    def build_capacity_constraints(self, time_slots: List[datetime]) -> List[Dict]:
        """Build canal capacity constraints"""
        constraints = []
        
        for canal_id, canal_data in self.canals.items():
            for t in range(len(time_slots)):
                # Find all gates on this canal
                gates_on_canal = [g for g, data in self.gates.items() if data["canal"] == canal_id]
                
                if gates_on_canal:
                    constraint = {
                        "name": f"capacity_{canal_id}_t{t}",
                        "type": "capacity",
                        "expression": {
                            "variables": [(f"flow_{g}_{t}", 1.0) for g in gates_on_canal],
                            "sense": "<=",
                            "rhs": canal_data["capacity"]
                        }
                    }
                    constraints.append(constraint)
        
        return constraints
    
    def build_hydraulic_constraints(self, time_slots: List[datetime]) -> List[Dict]:
        """Build hydraulic relationship constraints"""
        constraints = []
        
        # Gate flow equations: Q = Cd * A * sqrt(2g * dH)
        Cd = 0.6  # Discharge coefficient
        g = 9.81  # Gravity
        
        for gate_id, gate_data in self.gates.items():
            for t in range(len(time_slots)):
                # Simplified constraint: flow proportional to opening
                # In reality, this would involve water levels
                constraint = {
                    "name": f"hydraulic_{gate_id}_t{t}",
                    "type": "hydraulic",
                    "expression": {
                        "variables": [
                            (f"flow_{gate_id}_{t}", 1.0),
                            (f"opening_{gate_id}_{t}", -gate_data["maxFlow"] / 100.0)
                        ],
                        "sense": "=",
                        "rhs": 0.0
                    }
                }
                constraints.append(constraint)
        
        return constraints
    
    def build_team_constraints(self, time_slots: List[datetime], operation_days: List[int]) -> List[Dict]:
        """Build team capacity and routing constraints"""
        constraints = []
        
        for team in self.teams:
            team_id = team["team_code"]
            max_ops = team.get("max_operations_per_day", 30)
            
            # Daily operation limit
            for day in operation_days:
                # Time slots for this day
                day_slots = [t for t, ts in enumerate(time_slots) 
                           if ts.date() == ts.replace(hour=0).date() + timedelta(days=day)]
                
                if day_slots:
                    variables = []
                    for gate_id in self.gates:
                        for t in day_slots:
                            variables.append((f"assign_{team_id}_{gate_id}_{t}", 1.0))
                    
                    constraint = {
                        "name": f"team_capacity_{team_id}_day{day}",
                        "type": "team_capacity",
                        "expression": {
                            "variables": variables,
                            "sense": "<=",
                            "rhs": max_ops
                        }
                    }
                    constraints.append(constraint)
        
        return constraints
    
    def build_sequence_constraints(self, time_slots: List[datetime]) -> List[Dict]:
        """Build gravity flow sequencing constraints"""
        constraints = []
        
        for gate_id, gate_data in self.gates.items():
            upstream_gates = gate_data.get("upstream", [])
            
            for upstream_id in upstream_gates:
                if upstream_id in self.gates:
                    # Upstream gate must be operated before downstream
                    for t in range(1, len(time_slots)):
                        constraint = {
                            "name": f"sequence_{upstream_id}_before_{gate_id}_t{t}",
                            "type": "sequence",
                            "expression": {
                                "variables": [
                                    (f"operated_{gate_id}_{t}", 1.0),
                                    (f"operated_{upstream_id}_{t-1}", -1.0)
                                ],
                                "sense": "<=",
                                "rhs": 0.0
                            }
                        }
                        constraints.append(constraint)
        
        return constraints
    
    def build_continuity_constraints(self, time_slots: List[datetime]) -> List[Dict]:
        """Build water continuity constraints at nodes"""
        constraints = []
        
        # Group gates by junction nodes
        junctions = self._identify_junctions()
        
        for junction_id, junction_gates in junctions.items():
            for t in range(len(time_slots)):
                inflow_gates = junction_gates.get("inflow", [])
                outflow_gates = junction_gates.get("outflow", [])
                
                variables = []
                # Inflows (positive)
                for gate in inflow_gates:
                    variables.append((f"flow_{gate}_{t}", 1.0))
                # Outflows (negative)
                for gate in outflow_gates:
                    variables.append((f"flow_{gate}_{t}", -1.0))
                
                if variables:
                    constraint = {
                        "name": f"continuity_{junction_id}_t{t}",
                        "type": "continuity",
                        "expression": {
                            "variables": variables,
                            "sense": "=",
                            "rhs": 0.0
                        }
                    }
                    constraints.append(constraint)
        
        return constraints
    
    def _identify_junctions(self) -> Dict[str, Dict[str, List[str]]]:
        """Identify junction nodes in the network"""
        junctions = {}
        
        # Simplified junction identification
        # In reality, this would analyze the network topology
        junctions["J1"] = {
            "inflow": ["M(0,0)"],
            "outflow": ["M(0,2)", "M(0,3)", "M(0,4)"]
        }
        
        return junctions
    
    def build_custom_constraints(self) -> List[Dict]:
        """Build constraints from database configuration"""
        constraints = []
        
        for db_constraint in self.constraints:
            if db_constraint.is_active:
                constraint = {
                    "name": db_constraint.constraint_name,
                    "type": "custom",
                    "entity": db_constraint.entity_id,
                    "min_value": db_constraint.min_value,
                    "max_value": db_constraint.max_value,
                    "priority": db_constraint.priority,
                    "is_hard": db_constraint.is_hard_constraint,
                    "penalty": db_constraint.violation_penalty,
                }
                constraints.append(constraint)
        
        return constraints
    
    def build_all_constraints(self, demands: Dict, time_slots: List[datetime], operation_days: List[int]) -> Dict[str, List[Dict]]:
        """Build all constraints for the optimization model"""
        logger.info("Building optimization constraints")
        
        all_constraints = {
            "demand": self.build_demand_constraints(demands, time_slots),
            "capacity": self.build_capacity_constraints(time_slots),
            "hydraulic": self.build_hydraulic_constraints(time_slots),
            "team": self.build_team_constraints(time_slots, operation_days),
            "sequence": self.build_sequence_constraints(time_slots),
            "continuity": self.build_continuity_constraints(time_slots),
            "custom": self.build_custom_constraints(),
        }
        
        total_constraints = sum(len(c) for c in all_constraints.values())
        logger.info(f"Built {total_constraints} constraints")
        
        return all_constraints