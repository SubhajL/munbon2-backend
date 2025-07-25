from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from enum import Enum

class MovementStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"

class MovementPriority(str, Enum):
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"

class MovementTask(BaseModel):
    task_id: str
    sensor_id: str
    from_section_id: Optional[str]
    to_section_id: str
    from_coordinates: Optional[Dict[str, float]]
    to_coordinates: Dict[str, float]
    scheduled_date: datetime
    priority: MovementPriority
    estimated_duration_hours: float
    assigned_team_id: Optional[str] = None
    status: MovementStatus = MovementStatus.SCHEDULED
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    notes: Optional[str] = None
    travel_distance_km: float
    
class MovementSchedule(BaseModel):
    schedule_id: str
    week_start: datetime
    week_end: datetime
    total_movements: int
    tasks: List[MovementTask]
    total_distance_km: float
    estimated_total_hours: float
    teams_required: int
    optimization_score: float = Field(ge=0, le=1)
    
class FieldTeam(BaseModel):
    team_id: str
    name: str
    available_hours_per_week: float
    base_location: Dict[str, float]
    max_daily_distance_km: float
    current_assignments: List[str]  # task_ids
    
class MovementConstraints(BaseModel):
    max_movements_per_day: int = 3
    max_distance_per_team_per_day: float = 100.0
    min_sensor_deployment_days: int = 3
    prefer_morning_movements: bool = True
    avoid_weekends: bool = False
    buffer_time_hours: float = 1.0
    
class MovementOptimizationRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    sensor_placements: List[Dict[str, str]]  # {"sensor_id": x, "target_section": y}
    available_teams: List[str]
    constraints: MovementConstraints
    optimize_for: str = "distance"  # "distance", "time", "coverage"