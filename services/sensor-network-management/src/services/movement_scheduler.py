import os
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
import numpy as np
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import uuid

from models.movement import (
    MovementSchedule, MovementTask, MovementOptimizationRequest,
    MovementStatus, MovementPriority, FieldTeam, MovementConstraints
)
from models.sensor import SensorDB, SensorStatus
from utils.spatial import calculate_distance, get_section_coordinates

class MovementScheduler:
    """Schedule and optimize sensor movements"""
    
    def __init__(self):
        self.max_daily_movements = 3
        self.buffer_time_hours = 1.0
        self.work_hours_per_day = 8
        
    async def create_schedule(self, request: MovementOptimizationRequest,
                            db: AsyncSession) -> MovementSchedule:
        """Create optimized movement schedule"""
        # Get current sensor locations
        sensors = await self._get_sensors_to_move(request, db)
        
        # Get field teams
        teams = await self._get_available_teams(request.available_teams, db)
        
        # Create movement tasks
        tasks = await self._create_movement_tasks(
            sensors, request.sensor_placements, db
        )
        
        # Optimize task assignment and routing
        optimized_tasks = await self._optimize_routing(
            tasks, teams, request.constraints
        )
        
        # Calculate metrics
        total_distance = sum(t.travel_distance_km for t in optimized_tasks)
        total_hours = sum(t.estimated_duration_hours for t in optimized_tasks)
        
        schedule = MovementSchedule(
            schedule_id=str(uuid.uuid4()),
            week_start=request.start_date,
            week_end=request.end_date,
            total_movements=len(optimized_tasks),
            tasks=optimized_tasks,
            total_distance_km=total_distance,
            estimated_total_hours=total_hours,
            teams_required=len(set(t.assigned_team_id for t in optimized_tasks if t.assigned_team_id)),
            optimization_score=await self._calculate_optimization_score(optimized_tasks, teams)
        )
        
        # Save schedule to database
        await self._save_schedule(schedule, db)
        
        return schedule
    
    async def get_current_schedule(self, db: AsyncSession) -> Optional[MovementSchedule]:
        """Get current active movement schedule"""
        # Mock implementation - would query from database
        today = datetime.utcnow().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        
        # Create sample schedule
        tasks = [
            MovementTask(
                task_id="MT001",
                sensor_id="WL001",
                from_section_id="RMC-01",
                to_section_id="1L-1a",
                from_coordinates={"lat": 13.5, "lon": 100.5},
                to_coordinates={"lat": 13.52, "lon": 100.52},
                scheduled_date=week_start + timedelta(days=1),
                priority=MovementPriority.HIGH,
                estimated_duration_hours=2.5,
                assigned_team_id="TEAM01",
                status=MovementStatus.SCHEDULED,
                travel_distance_km=3.2
            ),
            MovementTask(
                task_id="MT002",
                sensor_id="WL002",
                from_section_id="1R-2a",
                to_section_id="2L-1a",
                from_coordinates={"lat": 13.48, "lon": 100.48},
                to_coordinates={"lat": 13.51, "lon": 100.51},
                scheduled_date=week_start + timedelta(days=2),
                priority=MovementPriority.NORMAL,
                estimated_duration_hours=2.0,
                assigned_team_id="TEAM01",
                status=MovementStatus.SCHEDULED,
                travel_distance_km=4.5
            )
        ]
        
        return MovementSchedule(
            schedule_id="SCH001",
            week_start=week_start,
            week_end=week_end,
            total_movements=len(tasks),
            tasks=tasks,
            total_distance_km=sum(t.travel_distance_km for t in tasks),
            estimated_total_hours=sum(t.estimated_duration_hours for t in tasks),
            teams_required=1,
            optimization_score=0.85
        )
    
    async def get_tasks(self, status: Optional[MovementStatus],
                       team_id: Optional[str], db: AsyncSession) -> List[MovementTask]:
        """Get movement tasks with filtering"""
        # Mock implementation
        tasks = [
            MovementTask(
                task_id="MT001",
                sensor_id="WL001",
                from_section_id="RMC-01",
                to_section_id="1L-1a",
                from_coordinates={"lat": 13.5, "lon": 100.5},
                to_coordinates={"lat": 13.52, "lon": 100.52},
                scheduled_date=datetime.utcnow() + timedelta(days=1),
                priority=MovementPriority.HIGH,
                estimated_duration_hours=2.5,
                assigned_team_id="TEAM01",
                status=MovementStatus.SCHEDULED,
                travel_distance_km=3.2
            )
        ]
        
        # Filter by status
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        # Filter by team
        if team_id:
            tasks = [t for t in tasks if t.assigned_team_id == team_id]
        
        return tasks
    
    async def update_task_status(self, task_id: str, status: MovementStatus,
                               notes: Optional[str], db: AsyncSession) -> MovementTask:
        """Update movement task status"""
        # Mock implementation
        task = MovementTask(
            task_id=task_id,
            sensor_id="WL001",
            from_section_id="RMC-01",
            to_section_id="1L-1a",
            from_coordinates={"lat": 13.5, "lon": 100.5},
            to_coordinates={"lat": 13.52, "lon": 100.52},
            scheduled_date=datetime.utcnow(),
            priority=MovementPriority.HIGH,
            estimated_duration_hours=2.5,
            assigned_team_id="TEAM01",
            status=status,
            travel_distance_km=3.2,
            notes=notes
        )
        
        if status == MovementStatus.IN_PROGRESS:
            task.actual_start_time = datetime.utcnow()
        elif status == MovementStatus.COMPLETED:
            task.actual_end_time = datetime.utcnow()
        
        return task
    
    async def get_teams(self, available_only: bool, 
                       db: AsyncSession) -> List[FieldTeam]:
        """Get field teams"""
        teams = [
            FieldTeam(
                team_id="TEAM01",
                name="North Zone Team",
                available_hours_per_week=40,
                base_location={"lat": 13.5, "lon": 100.5},
                max_daily_distance_km=100,
                current_assignments=["MT001", "MT002"]
            ),
            FieldTeam(
                team_id="TEAM02",
                name="South Zone Team",
                available_hours_per_week=40,
                base_location={"lat": 13.45, "lon": 100.45},
                max_daily_distance_km=100,
                current_assignments=[]
            )
        ]
        
        if available_only:
            teams = [t for t in teams if len(t.current_assignments) < 5]
        
        return teams
    
    async def calculate_optimization_score(self, schedule_id: Optional[str],
                                         db: AsyncSession) -> Dict[str, float]:
        """Calculate optimization metrics"""
        # Mock implementation
        return {
            "overall": 0.85,
            "distance": 0.82,  # How well we minimized travel distance
            "time": 0.88,      # How well we utilized available time
            "coverage": 0.85   # How well we covered priority areas
        }
    
    async def _get_sensors_to_move(self, request: MovementOptimizationRequest,
                                  db: AsyncSession) -> List[SensorDB]:
        """Get sensors that need to be moved"""
        sensor_ids = [p["sensor_id"] for p in request.sensor_placements]
        
        result = await db.execute(
            select(SensorDB).where(SensorDB.id.in_(sensor_ids))
        )
        return result.scalars().all()
    
    async def _create_movement_tasks(self, sensors: List[SensorDB],
                                   placements: List[Dict[str, str]],
                                   db: AsyncSession) -> List[MovementTask]:
        """Create movement tasks from placement requests"""
        tasks = []
        
        placement_map = {p["sensor_id"]: p["target_section"] for p in placements}
        
        for sensor in sensors:
            if sensor.id in placement_map:
                target_section = placement_map[sensor.id]
                target_coords = await get_section_coordinates(target_section, db)
                
                # Calculate distance
                if sensor.latitude and sensor.longitude:
                    distance = calculate_distance(
                        sensor.latitude, sensor.longitude,
                        target_coords["lat"], target_coords["lon"]
                    )
                else:
                    distance = 10.0  # Default distance
                
                # Estimate duration (30 min setup + travel time at 40 km/h)
                duration = 0.5 + (distance / 40.0)
                
                task = MovementTask(
                    task_id=str(uuid.uuid4()),
                    sensor_id=sensor.id,
                    from_section_id=sensor.current_section_id,
                    to_section_id=target_section,
                    from_coordinates={"lat": sensor.latitude or 0, "lon": sensor.longitude or 0},
                    to_coordinates=target_coords,
                    scheduled_date=datetime.utcnow() + timedelta(days=1),
                    priority=MovementPriority.NORMAL,
                    estimated_duration_hours=duration,
                    status=MovementStatus.SCHEDULED,
                    travel_distance_km=distance
                )
                tasks.append(task)
        
        return tasks
    
    async def _optimize_routing(self, tasks: List[MovementTask],
                              teams: List[FieldTeam],
                              constraints: MovementConstraints) -> List[MovementTask]:
        """Optimize task routing using OR-Tools"""
        if not tasks or not teams:
            return tasks
        
        # Create routing model
        manager, routing, solution = self._solve_vrp(tasks, teams, constraints)
        
        if solution:
            # Extract optimized routes
            optimized_tasks = self._extract_solution(
                manager, routing, solution, tasks, teams
            )
            return optimized_tasks
        else:
            # Fallback to simple assignment
            return self._simple_assignment(tasks, teams)
    
    def _solve_vrp(self, tasks: List[MovementTask], teams: List[FieldTeam],
                   constraints: MovementConstraints):
        """Solve Vehicle Routing Problem"""
        # Simplified VRP implementation
        # In production, would use full OR-Tools VRP solver
        
        # Create distance matrix
        n_locations = len(tasks) + len(teams)  # tasks + team bases
        distance_matrix = np.zeros((n_locations, n_locations))
        
        # Fill distance matrix
        for i in range(len(tasks)):
            for j in range(len(tasks)):
                if i != j:
                    distance_matrix[i][j] = calculate_distance(
                        tasks[i].to_coordinates["lat"],
                        tasks[i].to_coordinates["lon"],
                        tasks[j].from_coordinates["lat"],
                        tasks[j].from_coordinates["lon"]
                    )
        
        # For now, return None to use simple assignment
        return None, None, None
    
    def _simple_assignment(self, tasks: List[MovementTask],
                          teams: List[FieldTeam]) -> List[MovementTask]:
        """Simple round-robin assignment"""
        team_idx = 0
        
        for task in tasks:
            task.assigned_team_id = teams[team_idx].team_id
            team_idx = (team_idx + 1) % len(teams)
        
        return tasks
    
    async def _calculate_optimization_score(self, tasks: List[MovementTask],
                                          teams: List[FieldTeam]) -> float:
        """Calculate how well the schedule is optimized"""
        if not tasks:
            return 0.0
        
        # Distance efficiency
        total_distance = sum(t.travel_distance_km for t in tasks)
        min_possible_distance = len(tasks) * 2.0  # Assume minimum 2km per movement
        distance_score = min(min_possible_distance / total_distance, 1.0) if total_distance > 0 else 0
        
        # Time efficiency
        total_time = sum(t.estimated_duration_hours for t in tasks)
        available_time = len(teams) * 40  # 40 hours per week per team
        time_score = min(total_time / available_time, 1.0) if available_time > 0 else 0
        
        # Balance score (how evenly distributed among teams)
        team_tasks = {}
        for task in tasks:
            if task.assigned_team_id:
                team_tasks[task.assigned_team_id] = team_tasks.get(task.assigned_team_id, 0) + 1
        
        if team_tasks:
            avg_tasks = len(tasks) / len(teams)
            variance = sum((count - avg_tasks) ** 2 for count in team_tasks.values()) / len(teams)
            balance_score = 1 / (1 + variance)
        else:
            balance_score = 0
        
        # Combined score
        return (distance_score + time_score + balance_score) / 3
    
    async def _save_schedule(self, schedule: MovementSchedule, db: AsyncSession):
        """Save schedule to database"""
        # In production, would save to PostgreSQL
        pass
    
    async def _get_available_teams(self, team_ids: List[str],
                                  db: AsyncSession) -> List[FieldTeam]:
        """Get available field teams"""
        # Mock implementation
        all_teams = [
            FieldTeam(
                team_id="TEAM01",
                name="North Zone Team",
                available_hours_per_week=40,
                base_location={"lat": 13.5, "lon": 100.5},
                max_daily_distance_km=100,
                current_assignments=[]
            ),
            FieldTeam(
                team_id="TEAM02",
                name="South Zone Team",
                available_hours_per_week=40,
                base_location={"lat": 13.45, "lon": 100.45},
                max_daily_distance_km=100,
                current_assignments=[]
            )
        ]
        
        return [t for t in all_teams if t.team_id in team_ids]