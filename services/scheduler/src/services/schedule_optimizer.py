"""
Schedule Optimization Engine
Optimizes weekly irrigation schedules to minimize field team travel
while satisfying water demands and constraints
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime, date, timedelta
from dataclasses import dataclass
import structlog
from geopy.distance import geodesic
import asyncio

from ..db.connections import DatabaseManager
from ..schemas.schedule import ScheduleOperation, WeeklySchedule
from ..schemas.demands import SectionDemand

logger = structlog.get_logger()


@dataclass
class OptimizationResult:
    """Result of schedule optimization"""
    schedule: List[ScheduleOperation]
    total_travel_km: float
    demand_satisfaction: float
    computation_time_ms: int
    iterations: int
    warnings: List[str]


class ScheduleOptimizer:
    """
    Optimizes irrigation schedules using a multi-objective approach:
    1. Minimize field team travel distance
    2. Maximize demand satisfaction
    3. Balance workload across days/teams
    """
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        
        # Optimization parameters
        self.max_iterations = 1000
        self.convergence_threshold = 0.001
        self.tabu_list_size = 50
        
        # Field work constraints
        self.work_start_hour = 7
        self.work_end_hour = 17
        self.travel_speed_kmh = 40
        self.gate_operation_time_minutes = 30
        self.max_gates_per_day = 20
        
        # Teams and their base locations
        self.teams = {
            "Team_A": {"lat": 14.8200, "lon": 103.1500},
            "Team_B": {"lat": 14.8300, "lon": 103.1600}
        }
        
        # Gate locations cache
        self.gate_locations = {}
        self._load_gate_locations()
    
    def _load_gate_locations(self):
        """Load gate GPS locations from database"""
        # In real implementation, load from database
        # For now, use sample locations
        self.gate_locations = {
            "Source->M(0,0)": {"lat": 14.8234, "lon": 103.1567},
            "M(0,0)->M(0,2)": {"lat": 14.8245, "lon": 103.1578},
            "M(0,2)->Zone_2": {"lat": 14.8256, "lon": 103.1589},
            "M(0,0)->M(0,5)": {"lat": 14.8267, "lon": 103.1600},
            "M(0,5)->Zone_5": {"lat": 14.8278, "lon": 103.1611},
            # Add more gates as needed
        }
    
    async def optimize_schedule(
        self,
        demands: List[SectionDemand],
        week_start: date,
        constraints: Optional[Dict] = None
    ) -> OptimizationResult:
        """
        Main optimization function using Tabu Search algorithm
        """
        start_time = datetime.utcnow()
        
        try:
            # Step 1: Group demands by delivery paths
            delivery_paths = self._group_demands_by_path(demands)
            
            # Step 2: Determine gates that need manual operation
            manual_gates = await self._identify_manual_gates(delivery_paths)
            
            # Step 3: Create initial schedule using nearest neighbor
            initial_schedule = self._create_initial_schedule(
                manual_gates, week_start
            )
            
            # Step 4: Optimize using Tabu Search
            optimized_schedule = await self._tabu_search_optimization(
                initial_schedule, demands, constraints
            )
            
            # Step 5: Validate and finalize schedule
            final_schedule = self._validate_and_finalize(
                optimized_schedule, demands
            )
            
            # Calculate metrics
            total_travel = self._calculate_total_travel(final_schedule)
            satisfaction = self._calculate_demand_satisfaction(
                final_schedule, demands
            )
            
            computation_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )
            
            return OptimizationResult(
                schedule=final_schedule,
                total_travel_km=total_travel,
                demand_satisfaction=satisfaction,
                computation_time_ms=computation_time,
                iterations=self.max_iterations,
                warnings=self._generate_warnings(final_schedule, demands)
            )
            
        except Exception as e:
            logger.error(f"Schedule optimization failed: {e}")
            raise
    
    def _group_demands_by_path(
        self, 
        demands: List[SectionDemand]
    ) -> Dict[str, List[SectionDemand]]:
        """Group demands by their delivery paths"""
        paths = {}
        
        for demand in demands:
            # Determine delivery path based on zone
            zone = demand.zone
            if zone <= 3:
                path = "main_canal_upper"
            elif zone <= 6:
                path = "main_canal_lower"
            else:
                path = "lateral_canals"
            
            if path not in paths:
                paths[path] = []
            paths[path].append(demand)
        
        return paths
    
    async def _identify_manual_gates(
        self, 
        delivery_paths: Dict[str, List[SectionDemand]]
    ) -> List[Dict]:
        """Identify gates requiring manual operation"""
        manual_gates = []
        
        # Query flow monitoring service for gate states
        # For now, simulate with known manual gates
        manual_gate_ids = [
            "M(0,0)->M(0,2)",
            "M(0,5)->Zone_5",
            "M(2,0)->M(2,2)",
            "M(2,2)->Zone_8"
        ]
        
        for gate_id in manual_gate_ids:
            if gate_id in self.gate_locations:
                manual_gates.append({
                    "gate_id": gate_id,
                    "location": self.gate_locations[gate_id],
                    "current_opening": 0.5,  # Simulated
                    "target_opening": 0.8    # Based on demands
                })
        
        return manual_gates
    
    def _create_initial_schedule(
        self,
        manual_gates: List[Dict],
        week_start: date
    ) -> List[ScheduleOperation]:
        """Create initial schedule using nearest neighbor heuristic"""
        schedule = []
        
        # Divide gates between teams
        gates_per_team = len(manual_gates) // len(self.teams)
        
        # Schedule operations on Tuesday and Thursday
        operation_days = [
            (week_start + timedelta(days=1), "Tuesday"),
            (week_start + timedelta(days=3), "Thursday")
        ]
        
        for day_idx, (operation_date, day_name) in enumerate(operation_days):
            # Assign gates to teams for this day
            day_gates = manual_gates[
                day_idx * len(manual_gates) // 2:
                (day_idx + 1) * len(manual_gates) // 2
            ]
            
            for team_idx, (team_name, team_base) in enumerate(self.teams.items()):
                # Get team's gates using nearest neighbor
                team_gates = self._nearest_neighbor_route(
                    day_gates[
                        team_idx * len(day_gates) // len(self.teams):
                        (team_idx + 1) * len(day_gates) // len(self.teams)
                    ],
                    team_base
                )
                
                # Create operations
                scheduled_time = datetime.combine(
                    operation_date,
                    datetime.min.time().replace(hour=self.work_start_hour)
                )
                
                for gate in team_gates:
                    operation = ScheduleOperation(
                        operation_id=f"OP-{week_start.isocalendar()[1]}-{len(schedule)+1:03d}",
                        gate_id=gate["gate_id"],
                        action="adjust",
                        target_opening_m=gate["target_opening"],
                        scheduled_time=scheduled_time,
                        team_assigned=team_name,
                        day=day_name,
                        estimated_duration_minutes=self.gate_operation_time_minutes,
                        priority=1,
                        location=gate["location"]
                    )
                    schedule.append(operation)
                    
                    # Update scheduled time for next operation
                    travel_time = self._estimate_travel_time(
                        gate["location"],
                        team_gates[team_gates.index(gate) + 1]["location"]
                        if team_gates.index(gate) < len(team_gates) - 1
                        else team_base
                    )
                    scheduled_time += timedelta(
                        minutes=self.gate_operation_time_minutes + travel_time
                    )
        
        return schedule
    
    def _nearest_neighbor_route(
        self,
        gates: List[Dict],
        start_location: Dict[str, float]
    ) -> List[Dict]:
        """Order gates using nearest neighbor algorithm"""
        if not gates:
            return []
        
        ordered = []
        remaining = gates.copy()
        current_location = start_location
        
        while remaining:
            # Find nearest gate
            nearest = min(
                remaining,
                key=lambda g: geodesic(
                    (current_location["lat"], current_location["lon"]),
                    (g["location"]["lat"], g["location"]["lon"])
                ).km
            )
            
            ordered.append(nearest)
            remaining.remove(nearest)
            current_location = nearest["location"]
        
        return ordered
    
    async def _tabu_search_optimization(
        self,
        initial_schedule: List[ScheduleOperation],
        demands: List[SectionDemand],
        constraints: Optional[Dict]
    ) -> List[ScheduleOperation]:
        """
        Optimize schedule using Tabu Search metaheuristic
        """
        current_solution = initial_schedule.copy()
        best_solution = current_solution.copy()
        best_cost = self._calculate_cost(current_solution, demands)
        
        tabu_list = []
        iteration = 0
        
        while iteration < self.max_iterations:
            # Generate neighborhood solutions
            neighbors = self._generate_neighbors(current_solution)
            
            # Find best non-tabu neighbor
            best_neighbor = None
            best_neighbor_cost = float('inf')
            
            for neighbor in neighbors:
                if not self._is_tabu(neighbor, tabu_list):
                    cost = self._calculate_cost(neighbor, demands)
                    if cost < best_neighbor_cost:
                        best_neighbor = neighbor
                        best_neighbor_cost = cost
            
            # Update current solution
            if best_neighbor:
                current_solution = best_neighbor
                tabu_list.append(self._get_move_signature(best_neighbor))
                
                # Maintain tabu list size
                if len(tabu_list) > self.tabu_list_size:
                    tabu_list.pop(0)
                
                # Update best solution if improved
                if best_neighbor_cost < best_cost:
                    best_solution = best_neighbor.copy()
                    best_cost = best_neighbor_cost
            
            iteration += 1
            
            # Check convergence
            if iteration % 100 == 0:
                logger.debug(f"Iteration {iteration}, best cost: {best_cost}")
        
        return best_solution
    
    def _generate_neighbors(
        self, 
        schedule: List[ScheduleOperation]
    ) -> List[List[ScheduleOperation]]:
        """Generate neighborhood solutions using various operators"""
        neighbors = []
        
        # Operator 1: Swap operations between teams
        for i in range(len(schedule) - 1):
            for j in range(i + 1, len(schedule)):
                if (schedule[i].team_assigned != schedule[j].team_assigned and
                    schedule[i].day == schedule[j].day):
                    neighbor = schedule.copy()
                    neighbor[i].team_assigned, neighbor[j].team_assigned = \
                        neighbor[j].team_assigned, neighbor[i].team_assigned
                    neighbors.append(neighbor)
        
        # Operator 2: Move operation to different day
        for i, op in enumerate(schedule):
            if op.day == "Tuesday":
                neighbor = schedule.copy()
                neighbor[i].day = "Thursday"
                neighbor[i].scheduled_time = neighbor[i].scheduled_time + timedelta(days=2)
                neighbors.append(neighbor)
            elif op.day == "Thursday":
                neighbor = schedule.copy()
                neighbor[i].day = "Tuesday"
                neighbor[i].scheduled_time = neighbor[i].scheduled_time - timedelta(days=2)
                neighbors.append(neighbor)
        
        # Operator 3: Reorder operations within team/day
        teams_days = {}
        for i, op in enumerate(schedule):
            key = (op.team_assigned, op.day)
            if key not in teams_days:
                teams_days[key] = []
            teams_days[key].append(i)
        
        for indices in teams_days.values():
            if len(indices) > 2:
                # Try 2-opt improvement
                for i in range(len(indices) - 1):
                    for j in range(i + 2, len(indices)):
                        neighbor = schedule.copy()
                        # Reverse sequence
                        reversed_ops = [neighbor[k] for k in indices[i:j+1]][::-1]
                        for k, idx in enumerate(indices[i:j+1]):
                            neighbor[idx] = reversed_ops[k]
                        neighbors.append(neighbor)
        
        return neighbors[:50]  # Limit neighborhood size
    
    def _calculate_cost(
        self,
        schedule: List[ScheduleOperation],
        demands: List[SectionDemand]
    ) -> float:
        """Calculate multi-objective cost function"""
        # Component 1: Travel distance
        travel_cost = self._calculate_total_travel(schedule)
        
        # Component 2: Demand satisfaction penalty
        satisfaction = self._calculate_demand_satisfaction(schedule, demands)
        demand_penalty = (1 - satisfaction) * 100
        
        # Component 3: Workload balance
        balance_penalty = self._calculate_balance_penalty(schedule)
        
        # Weighted sum
        total_cost = (
            0.5 * travel_cost +
            0.3 * demand_penalty +
            0.2 * balance_penalty
        )
        
        return total_cost
    
    def _calculate_total_travel(
        self, 
        schedule: List[ScheduleOperation]
    ) -> float:
        """Calculate total travel distance for all teams"""
        total_km = 0.0
        
        # Group by team and day
        team_day_ops = {}
        for op in schedule:
            key = (op.team_assigned, op.day)
            if key not in team_day_ops:
                team_day_ops[key] = []
            team_day_ops[key].append(op)
        
        # Calculate travel for each team/day
        for (team, day), ops in team_day_ops.items():
            if not ops:
                continue
            
            # Sort by scheduled time
            ops.sort(key=lambda x: x.scheduled_time)
            
            # Start from base
            team_base = self.teams[team]
            current_loc = team_base
            
            # Travel to each gate
            for op in ops:
                gate_loc = op.location
                distance = geodesic(
                    (current_loc["lat"], current_loc["lon"]),
                    (gate_loc["lat"], gate_loc["lon"])
                ).km
                total_km += distance
                current_loc = gate_loc
            
            # Return to base
            distance = geodesic(
                (current_loc["lat"], current_loc["lon"]),
                (team_base["lat"], team_base["lon"])
            ).km
            total_km += distance
        
        return total_km
    
    def _calculate_demand_satisfaction(
        self,
        schedule: List[ScheduleOperation],
        demands: List[SectionDemand]
    ) -> float:
        """Calculate percentage of demands satisfied"""
        if not demands:
            return 1.0
        
        # Simplified: assume each operation contributes to demand
        # In reality, would check hydraulic feasibility
        scheduled_gates = set(op.gate_id for op in schedule)
        required_gates = set()
        
        for demand in demands:
            # Map demand to required gates (simplified)
            if demand.zone <= 3:
                required_gates.add("M(0,0)->M(0,2)")
                required_gates.add("M(0,2)->Zone_2")
            elif demand.zone <= 6:
                required_gates.add("M(0,0)->M(0,5)")
                required_gates.add("M(0,5)->Zone_5")
        
        if not required_gates:
            return 1.0
        
        covered = len(scheduled_gates.intersection(required_gates))
        return covered / len(required_gates)
    
    def _calculate_balance_penalty(
        self, 
        schedule: List[ScheduleOperation]
    ) -> float:
        """Calculate workload balance penalty"""
        # Count operations per team per day
        workload = {}
        for op in schedule:
            key = (op.team_assigned, op.day)
            workload[key] = workload.get(key, 0) + 1
        
        if not workload:
            return 0.0
        
        # Calculate standard deviation
        counts = list(workload.values())
        mean = sum(counts) / len(counts)
        variance = sum((x - mean) ** 2 for x in counts) / len(counts)
        std_dev = variance ** 0.5
        
        # Normalize to 0-100 scale
        return min(std_dev * 10, 100)
    
    def _is_tabu(
        self,
        solution: List[ScheduleOperation],
        tabu_list: List[str]
    ) -> bool:
        """Check if solution is in tabu list"""
        signature = self._get_move_signature(solution)
        return signature in tabu_list
    
    def _get_move_signature(
        self, 
        solution: List[ScheduleOperation]
    ) -> str:
        """Generate signature for solution"""
        # Simple signature based on team assignments
        assignments = sorted([
            f"{op.gate_id}:{op.team_assigned}:{op.day}"
            for op in solution
        ])
        return "|".join(assignments)
    
    def _estimate_travel_time(
        self,
        from_location: Dict[str, float],
        to_location: Dict[str, float]
    ) -> int:
        """Estimate travel time in minutes"""
        distance_km = geodesic(
            (from_location["lat"], from_location["lon"]),
            (to_location["lat"], to_location["lon"])
        ).km
        
        travel_minutes = int((distance_km / self.travel_speed_kmh) * 60)
        return max(travel_minutes, 5)  # Minimum 5 minutes
    
    def _validate_and_finalize(
        self,
        schedule: List[ScheduleOperation],
        demands: List[SectionDemand]
    ) -> List[ScheduleOperation]:
        """Validate and finalize the optimized schedule"""
        # Sort by team and time
        schedule.sort(key=lambda x: (x.team_assigned, x.scheduled_time))
        
        # Adjust times to ensure feasibility
        for team in self.teams:
            team_ops = [op for op in schedule if op.team_assigned == team]
            
            for i in range(1, len(team_ops)):
                prev_op = team_ops[i-1]
                curr_op = team_ops[i]
                
                # Calculate minimum time needed
                travel_time = self._estimate_travel_time(
                    prev_op.location,
                    curr_op.location
                )
                min_time = prev_op.scheduled_time + timedelta(
                    minutes=prev_op.estimated_duration_minutes + travel_time
                )
                
                # Adjust if needed
                if curr_op.scheduled_time < min_time:
                    curr_op.scheduled_time = min_time
        
        return schedule
    
    def _generate_warnings(
        self,
        schedule: List[ScheduleOperation],
        demands: List[SectionDemand]
    ) -> List[str]:
        """Generate warnings about the schedule"""
        warnings = []
        
        # Check for long work days
        for team in self.teams:
            for day in ["Tuesday", "Thursday"]:
                day_ops = [
                    op for op in schedule 
                    if op.team_assigned == team and op.day == day
                ]
                if day_ops:
                    start = min(op.scheduled_time for op in day_ops)
                    end = max(
                        op.scheduled_time + timedelta(minutes=op.estimated_duration_minutes)
                        for op in day_ops
                    )
                    work_hours = (end - start).total_seconds() / 3600
                    
                    if work_hours > 10:
                        warnings.append(
                            f"{team} has {work_hours:.1f} hour workday on {day}"
                        )
        
        # Check demand coverage
        satisfaction = self._calculate_demand_satisfaction(schedule, demands)
        if satisfaction < 0.9:
            warnings.append(
                f"Only {satisfaction*100:.0f}% of demands are covered"
            )
        
        # Check travel distance
        total_travel = self._calculate_total_travel(schedule)
        if total_travel > 200:
            warnings.append(
                f"Total travel distance is {total_travel:.0f} km"
            )
        
        return warnings