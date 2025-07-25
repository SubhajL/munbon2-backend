"""
Schedule-related Pydantic schemas
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime, date
from pydantic import BaseModel, Field, validator


class ScheduleStatus(str, Enum):
    """Schedule status options"""
    DRAFT = "draft"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OperationStatus(str, Enum):
    """Operation status options"""
    SCHEDULED = "scheduled"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class ScheduleOperation(BaseModel):
    """Individual gate operation in schedule"""
    operation_id: str
    gate_id: str
    action: str = Field(description="open, close, or adjust")
    target_opening_m: float = Field(ge=0, description="Target gate opening in meters")
    scheduled_time: datetime
    team_assigned: Optional[str] = None
    day: str = Field(description="Day of week")
    estimated_duration_minutes: int = Field(default=30)
    priority: int = Field(ge=1, le=10, default=5)
    location: Dict[str, float] = Field(description="GPS coordinates")
    status: OperationStatus = Field(default=OperationStatus.SCHEDULED)
    completion_time: Optional[datetime] = None
    actual_opening_m: Optional[float] = None
    notes: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WeeklySchedule(BaseModel):
    """Complete weekly irrigation schedule"""
    week: str = Field(description="Week in YYYY-WW format")
    status: ScheduleStatus = Field(default=ScheduleStatus.DRAFT)
    operations: List[ScheduleOperation]
    created_at: datetime
    updated_at: datetime
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    total_demand_m3: Optional[float] = None
    expected_deliveries: Optional[Dict[str, float]] = None
    optimization_metrics: Optional[Dict[str, Any]] = None
    
    @validator('week')
    def validate_week_format(cls, v):
        try:
            year, week = v.split('-')
            year = int(year)
            week = int(week)
            if week < 1 or week > 53:
                raise ValueError
        except:
            raise ValueError("Week must be in YYYY-WW format")
        return v


class ScheduleUpdate(BaseModel):
    """Update request for schedule status"""
    status: ScheduleStatus
    notes: Optional[str] = None
    approved_by: Optional[str] = None


class ScheduleOptimizationRequest(BaseModel):
    """Request to optimize schedule"""
    force_regenerate: bool = Field(default=False)
    optimization_params: Optional[Dict[str, Any]] = Field(
        default={
            "max_iterations": 1000,
            "travel_weight": 0.5,
            "demand_weight": 0.3,
            "balance_weight": 0.2
        }
    )
    constraints: Optional[Dict[str, Any]] = None


class ScheduleConflict(BaseModel):
    """Conflict in schedule"""
    conflict_type: str
    severity: str = Field(description="low, medium, high")
    affected_operations: List[str]
    description: str
    resolution_options: List[str]


class OperationCompletion(BaseModel):
    """Completion report for operation"""
    operation_id: str
    completion_time: datetime
    actual_opening_m: float
    operator_id: str
    photos: Optional[List[str]] = None
    notes: Optional[str] = None
    issues_encountered: Optional[List[str]] = None