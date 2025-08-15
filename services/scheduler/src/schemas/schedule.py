from typing import Dict, List, Optional, Any
from datetime import datetime, date
from uuid import UUID

from pydantic import BaseModel, Field, validator


class ScheduleGenerateRequest(BaseModel):
    """Request to generate a new schedule"""
    week_number: int = Field(..., ge=1, le=53, description="Week number (1-53)")
    year: int = Field(..., ge=2024, le=2030, description="Year")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Custom constraints")
    operation_days: Optional[List[int]] = Field(
        None, 
        description="Days of week for operations (0=Monday, 6=Sunday)"
    )
    max_operations_per_day: Optional[int] = Field(None, description="Max operations per day")
    
    @validator("operation_days")
    def validate_operation_days(cls, v):
        if v is not None:
            if not all(0 <= day <= 6 for day in v):
                raise ValueError("Operation days must be between 0 (Monday) and 6 (Sunday)")
        return v


class ScheduleBase(BaseModel):
    """Base schedule model"""
    schedule_code: str
    week_number: int
    year: int
    start_date: date
    end_date: date
    status: str
    version: int
    total_water_demand_m3: float
    total_water_allocated_m3: Optional[float]
    efficiency_percent: Optional[float]
    total_operations: int
    field_days: List[date]
    total_travel_km: Optional[float]
    estimated_labor_hours: Optional[float]


class ScheduleCreate(BaseModel):
    """Create schedule model"""
    week_number: int
    year: int
    constraints: Optional[Dict[str, Any]] = None


class ScheduleUpdate(BaseModel):
    """Update schedule model"""
    status: Optional[str] = None
    notes: Optional[str] = None
    weather_forecast: Optional[Dict[str, Any]] = None


class ScheduleResponse(ScheduleBase):
    """Schedule response model"""
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]
    created_by: str
    updated_by: Optional[str]
    approved_at: Optional[datetime]
    approved_by: Optional[str]
    activated_at: Optional[datetime]
    optimization_time_seconds: Optional[float]
    optimization_iterations: Optional[int]
    objective_value: Optional[float]
    constraints_summary: Optional[Dict[str, Any]]
    weather_forecast: Optional[Dict[str, Any]]
    notes: Optional[str]
    
    class Config:
        orm_mode = True


class ScheduleSummary(BaseModel):
    """Schedule summary for list views"""
    id: UUID
    schedule_code: str
    week_number: int
    year: int
    status: str
    total_operations: int
    efficiency_percent: Optional[float]
    created_at: datetime
    
    class Config:
        orm_mode = True


class ScheduleAnalytics(BaseModel):
    """Schedule analytics"""
    schedule_id: UUID
    performance_metrics: Dict[str, float]
    resource_utilization: Dict[str, float]
    water_delivery_stats: Dict[str, float]
    team_performance: Dict[str, Any]
    deviation_analysis: Dict[str, Any]