"""
Operation schemas for the scheduler service.

These schemas define the data structures for gate operations,
including status updates, history, and summaries.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date, time
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, validator


class OperationStatusEnum(str, Enum):
    """Valid operation statuses"""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"


class OperationType(str, Enum):
    """Types of gate operations"""
    OPEN = "open"
    CLOSE = "close"
    ADJUST = "adjust"
    MAINTAIN = "maintain"
    INSPECT = "inspect"


class OperationPriority(str, Enum):
    """Operation priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class GpsCoordinates(BaseModel):
    """GPS coordinates for verification"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = Field(None, ge=0, description="Accuracy in meters")
    timestamp: Optional[datetime] = None


class OperationStatus(BaseModel):
    """Operation status update from field teams"""
    status: OperationStatusEnum
    timestamp: Optional[datetime] = None
    actual_opening_percent: Optional[float] = Field(None, ge=0, le=100)
    actual_flow: Optional[float] = Field(None, ge=0, description="Actual flow in m³/s")
    notes: Optional[str] = Field(None, max_length=500)
    failure_reason: Optional[str] = Field(None, max_length=500)
    verification_photos: Optional[List[str]] = Field(None, description="URLs of verification photos")
    gps_coordinates: Optional[GpsCoordinates] = None
    
    @validator('timestamp', pre=True, always=True)
    def set_timestamp(cls, v):
        return v or datetime.utcnow()
    
    @validator('failure_reason')
    def failure_reason_required_for_failed(cls, v, values):
        if values.get('status') == OperationStatusEnum.FAILED and not v:
            raise ValueError("failure_reason is required when status is 'failed'")
        return v


class OperationBase(BaseModel):
    """Base schema for operations"""
    gate_id: str = Field(..., description="Gate identifier")
    gate_name: Optional[str] = None
    team_id: str = Field(..., description="Assigned team ID")
    team_name: Optional[str] = None
    operation_type: OperationType
    operation_date: date
    planned_start_time: time
    planned_end_time: time
    duration_minutes: int = Field(..., ge=1)
    operation_sequence: int = Field(..., ge=1)
    target_opening_percent: float = Field(..., ge=0, le=100)
    target_flow_rate: float = Field(..., ge=0, description="Target flow in m³/s")
    
    # Location info
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    location_description: Optional[str] = None
    
    # Upstream/downstream gates
    upstream_gates: Optional[List[str]] = Field(default_factory=list)
    downstream_gates: Optional[List[str]] = Field(default_factory=list)
    
    # Instructions
    special_instructions: Optional[str] = None
    safety_notes: Optional[str] = None


class OperationCreate(OperationBase):
    """Schema for creating operations"""
    priority: OperationPriority = OperationPriority.NORMAL
    requires_verification: bool = True
    estimated_travel_time: Optional[int] = Field(None, ge=0, description="Travel time in minutes")


class OperationUpdate(BaseModel):
    """Schema for updating operation details"""
    team_id: Optional[str] = None
    operation_date: Optional[date] = None
    planned_start_time: Optional[time] = None
    planned_end_time: Optional[time] = None
    target_opening_percent: Optional[float] = Field(None, ge=0, le=100)
    special_instructions: Optional[str] = None
    priority: Optional[OperationPriority] = None
    
    class Config:
        extra = "forbid"


class OperationResponse(OperationBase):
    """Schema for operation responses"""
    id: UUID
    schedule_id: UUID
    status: OperationStatusEnum = OperationStatusEnum.SCHEDULED
    
    # Actual execution data
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    actual_opening_percent: Optional[float] = None
    actual_flow_achieved: Optional[float] = None
    
    # Verification
    verification_photos: Optional[List[str]] = None
    actual_latitude: Optional[float] = None
    actual_longitude: Optional[float] = None
    
    # Status info
    completion_notes: Optional[str] = None
    failure_reason: Optional[str] = None
    requires_rescheduling: bool = False
    
    # Rescheduling info
    rescheduled_at: Optional[datetime] = None
    rescheduled_by: Optional[str] = None
    reschedule_reason: Optional[str] = None
    
    # Metadata
    created_at: datetime
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            time: lambda v: v.isoformat(),
        }


class OperationSummary(BaseModel):
    """Simplified operation summary for mobile/dashboard views"""
    operation_id: UUID
    gate_id: str
    gate_name: Optional[str]
    team_id: str
    planned_time: time
    status: OperationStatusEnum
    location: Dict[str, Any] = Field(..., description="Location info with lat/lon")
    action: str = Field(..., description="Human-readable action description")
    priority: OperationPriority
    
    class Config:
        json_encoders = {
            time: lambda v: v.isoformat(),
        }


class GateOperationHistory(BaseModel):
    """Historical operation data for a gate"""
    operation_id: UUID
    schedule_id: UUID
    operation_date: date
    planned_time: time
    actual_time: Optional[datetime]
    team_id: str
    team_name: Optional[str]
    target_opening: float
    actual_opening: Optional[float]
    status: OperationStatusEnum
    notes: Optional[str]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            date: lambda v: v.isoformat(),
            time: lambda v: v.isoformat(),
        }


class OperationBatch(BaseModel):
    """Batch of operations for creation"""
    operations: List[OperationCreate]
    schedule_id: UUID
    auto_sequence: bool = Field(True, description="Auto-assign sequence numbers")
    
    @validator('operations')
    def validate_operations(cls, v):
        if not v:
            raise ValueError("At least one operation must be provided")
        if len(v) > 1000:
            raise ValueError("Maximum 1000 operations per batch")
        return v


class OperationPerformance(BaseModel):
    """Operation performance metrics"""
    operation_id: UUID
    planned_duration_minutes: int
    actual_duration_minutes: Optional[int]
    delay_minutes: Optional[int]
    flow_accuracy_percent: Optional[float]
    opening_accuracy_percent: Optional[float]
    verification_complete: bool
    issues_reported: List[str] = Field(default_factory=list)
    
    @property
    def on_time(self) -> bool:
        """Check if operation was completed on time"""
        return self.delay_minutes is not None and self.delay_minutes <= 30
    
    @property
    def accurate(self) -> bool:
        """Check if operation achieved target accuracy"""
        return (
            self.flow_accuracy_percent is not None and 
            self.flow_accuracy_percent >= 90 and
            self.opening_accuracy_percent is not None and
            self.opening_accuracy_percent >= 95
        )