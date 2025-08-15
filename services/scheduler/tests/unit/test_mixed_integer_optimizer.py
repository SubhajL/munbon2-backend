"""
Unit tests for Mixed Integer Linear Programming optimizer.
"""

import pytest
import numpy as np
from datetime import date, time

from src.algorithms.mixed_integer_optimizer import MixedIntegerOptimizer
from src.schemas.demands import DeliveryPath


class TestMixedIntegerOptimizer:
    """Test MILP optimization algorithm"""
    
    @pytest.fixture
    def sample_network(self):
        """Sample hydraulic network for testing"""
        return {
            "gates": {
                "GATE-001": {
                    "id": "GATE-001",
                    "name": "Main Gate 1",
                    "type": "main",
                    "max_flow": 10.0,
                    "min_flow": 0.5,
                    "location": (13.7563, 100.5018),
                    "upstream": [],
                    "downstream": ["GATE-002", "GATE-003"],
                },
                "GATE-002": {
                    "id": "GATE-002",
                    "name": "Secondary Gate 2",
                    "type": "secondary",
                    "max_flow": 5.0,
                    "min_flow": 0.2,
                    "location": (13.7600, 100.5050),
                    "upstream": ["GATE-001"],
                    "downstream": ["GATE-004"],
                },
                "GATE-003": {
                    "id": "GATE-003",
                    "name": "Secondary Gate 3",
                    "type": "secondary",
                    "max_flow": 5.0,
                    "min_flow": 0.2,
                    "location": (13.7550, 100.5100),
                    "upstream": ["GATE-001"],
                    "downstream": ["GATE-005"],
                },
            },
            "canals": {
                "CANAL-001": {
                    "id": "CANAL-001",
                    "from_gate": "GATE-001",
                    "to_gates": ["GATE-002", "GATE-003"],
                    "capacity": 15.0,
                    "length_km": 5.0,
                },
            }
        }
    
    @pytest.fixture
    def sample_delivery_paths(self):
        """Sample delivery paths for testing"""
        return [
            DeliveryPath(
                path_id="PATH-001",
                zone_id="ZONE-001",
                gates=["GATE-001", "GATE-002", "GATE-004"],
                total_demand_m3=5000.0,
                priority=1,
                delivery_window_days=2,
            ),
            DeliveryPath(
                path_id="PATH-002",
                zone_id="ZONE-002",
                gates=["GATE-001", "GATE-003", "GATE-005"],
                total_demand_m3=3000.0,
                priority=2,
                delivery_window_days=2,
            ),
        ]
    
    @pytest.fixture
    def sample_teams(self):
        """Sample teams for testing"""
        return {
            "TEAM-001": {
                "id": "TEAM-001",
                "name": "Team Alpha",
                "base_location": (13.7563, 100.5018),
                "capacity_per_day": 8,
                "operating_hours": (time(6, 0), time(18, 0)),
            },
            "TEAM-002": {
                "id": "TEAM-002",
                "name": "Team Beta",
                "base_location": (13.7600, 100.5100),
                "capacity_per_day": 8,
                "operating_hours": (time(6, 0), time(18, 0)),
            },
        }
    
    @pytest.fixture
    def optimizer(self):
        """Create optimizer instance"""
        return MixedIntegerOptimizer()
    
    def test_optimizer_initialization(self, optimizer):
        """Test optimizer is properly initialized"""
        assert optimizer is not None
        assert optimizer.solver is not None
        assert optimizer.time_horizon == 7  # Weekly schedule
    
    def test_build_optimization_model(self, optimizer, sample_network, sample_delivery_paths, sample_teams):
        """Test building the optimization model"""
        constraints = {
            "max_daily_operations": 10,
            "min_flow_rate": 0.5,
            "team_overtime_allowed": False,
        }
        
        problem = optimizer.build_model(
            network=sample_network,
            delivery_paths=sample_delivery_paths,
            teams=sample_teams,
            constraints=constraints,
            days=2,
        )
        
        assert problem is not None
        assert len(problem.variables()) > 0
        assert len(problem.constraints) > 0
    
    def test_solve_simple_schedule(self, optimizer, sample_network, sample_delivery_paths, sample_teams):
        """Test solving a simple scheduling problem"""
        constraints = {
            "max_daily_operations": 10,
            "min_flow_rate": 0.5,
            "team_overtime_allowed": False,
        }
        
        solution = optimizer.solve(
            network=sample_network,
            delivery_paths=sample_delivery_paths,
            teams=sample_teams,
            constraints=constraints,
            days=2,
        )
        
        assert solution is not None
        assert solution["status"] in ["Optimal", "Feasible"]
        assert "operations" in solution
        assert len(solution["operations"]) > 0
    
    def test_demand_satisfaction_constraint(self, optimizer, sample_network, sample_delivery_paths, sample_teams):
        """Test that all demands are satisfied"""
        constraints = {
            "max_daily_operations": 20,
            "min_flow_rate": 0.5,
            "team_overtime_allowed": False,
        }
        
        solution = optimizer.solve(
            network=sample_network,
            delivery_paths=sample_delivery_paths,
            teams=sample_teams,
            constraints=constraints,
            days=2,
        )
        
        # Check total water delivered
        total_delivered = sum(op["flow_rate"] * op["duration_hours"] * 3600 for op in solution["operations"])
        total_demand = sum(path.total_demand_m3 for path in sample_delivery_paths)
        
        # Allow small tolerance for numerical precision
        assert abs(total_delivered - total_demand) / total_demand < 0.01
    
    def test_team_capacity_constraint(self, optimizer, sample_network, sample_delivery_paths, sample_teams):
        """Test that team capacity is not exceeded"""
        constraints = {
            "max_daily_operations": 5,  # Restrictive constraint
            "min_flow_rate": 0.5,
            "team_overtime_allowed": False,
        }
        
        solution = optimizer.solve(
            network=sample_network,
            delivery_paths=sample_delivery_paths,
            teams=sample_teams,
            constraints=constraints,
            days=2,
        )
        
        # Count operations per team per day
        team_ops_per_day = {}
        for op in solution["operations"]:
            key = (op["team_id"], op["day"])
            team_ops_per_day[key] = team_ops_per_day.get(key, 0) + 1
        
        # Check no team exceeds daily capacity
        for (team_id, day), count in team_ops_per_day.items():
            assert count <= sample_teams[team_id]["capacity_per_day"]
    
    def test_flow_constraints(self, optimizer, sample_network, sample_delivery_paths, sample_teams):
        """Test that flow constraints are respected"""
        constraints = {
            "max_daily_operations": 20,
            "min_flow_rate": 0.5,
            "team_overtime_allowed": False,
        }
        
        solution = optimizer.solve(
            network=sample_network,
            delivery_paths=sample_delivery_paths,
            teams=sample_teams,
            constraints=constraints,
            days=2,
        )
        
        # Check all flows are within gate limits
        for op in solution["operations"]:
            gate = sample_network["gates"][op["gate_id"]]
            assert op["flow_rate"] >= gate["min_flow"]
            assert op["flow_rate"] <= gate["max_flow"]
    
    def test_objective_minimization(self, optimizer, sample_network, sample_delivery_paths, sample_teams):
        """Test that objective function is minimized"""
        # Run with different weights
        constraints = {
            "max_daily_operations": 20,
            "min_flow_rate": 0.5,
            "team_overtime_allowed": False,
        }
        
        # Emphasize travel minimization
        optimizer.weight_travel = 10.0
        optimizer.weight_changes = 1.0
        optimizer.weight_spillage = 1.0
        
        solution1 = optimizer.solve(
            network=sample_network,
            delivery_paths=sample_delivery_paths,
            teams=sample_teams,
            constraints=constraints,
            days=2,
        )
        
        # Emphasize gate change minimization
        optimizer.weight_travel = 1.0
        optimizer.weight_changes = 10.0
        optimizer.weight_spillage = 1.0
        
        solution2 = optimizer.solve(
            network=sample_network,
            delivery_paths=sample_delivery_paths,
            teams=sample_teams,
            constraints=constraints,
            days=2,
        )
        
        # Solutions should be different based on weights
        assert solution1["objective_value"] != solution2["objective_value"]
    
    def test_infeasible_problem(self, optimizer, sample_network, sample_delivery_paths, sample_teams):
        """Test handling of infeasible problems"""
        # Make problem infeasible with very restrictive constraints
        constraints = {
            "max_daily_operations": 1,  # Too restrictive
            "min_flow_rate": 20.0,  # Impossible flow rate
            "team_overtime_allowed": False,
        }
        
        solution = optimizer.solve(
            network=sample_network,
            delivery_paths=sample_delivery_paths,
            teams=sample_teams,
            constraints=constraints,
            days=1,
        )
        
        assert solution["status"] == "Infeasible"
        assert "error" in solution
    
    def test_gravity_flow_sequencing(self, optimizer, sample_network, sample_delivery_paths, sample_teams):
        """Test that gravity flow sequencing is respected"""
        constraints = {
            "max_daily_operations": 20,
            "min_flow_rate": 0.5,
            "team_overtime_allowed": False,
        }
        
        solution = optimizer.solve(
            network=sample_network,
            delivery_paths=sample_delivery_paths,
            teams=sample_teams,
            constraints=constraints,
            days=2,
        )
        
        # Check upstream gates are operated before downstream
        operations_by_time = sorted(solution["operations"], key=lambda x: (x["day"], x["start_time"]))
        
        for i, op in enumerate(operations_by_time):
            gate = sample_network["gates"][op["gate_id"]]
            
            # Find operations on upstream gates
            for upstream_gate_id in gate["upstream"]:
                upstream_ops = [
                    j for j, other_op in enumerate(operations_by_time)
                    if other_op["gate_id"] == upstream_gate_id and other_op["day"] == op["day"]
                ]
                
                # Upstream operations should come before this operation
                for upstream_idx in upstream_ops:
                    assert upstream_idx < i, f"Upstream gate {upstream_gate_id} should be operated before {op['gate_id']}"