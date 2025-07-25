"""
Field Operations Pydantic schemas
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime, date
from pydantic import BaseModel, Field, validator


class InstructionType(str, Enum):
    """Type of field instruction"""
    GATE_OPERATION = "gate_operation"
    MEASUREMENT = "measurement"
    INSPECTION = "inspection"
    MAINTENANCE = "maintenance"


class TeamStatus(str, Enum):
    """Field team status"""
    AVAILABLE = "available"
    EN_ROUTE = "en_route"
    WORKING = "working"
    BREAK = "break"
    OFFLINE = "offline"
    EMERGENCY = "emergency"


class FieldInstruction(BaseModel):
    """Instruction for field team"""
    instruction_id: str
    type: InstructionType
    gate_id: str
    location: Dict[str, float] = Field(description="GPS coordinates")
    action: str
    target_opening_m: float
    current_opening_m: float
    physical_markers: str = Field(
        description="Physical reference for gate position"
    )
    photo_required: bool = Field(default=True)
    estimated_duration_minutes: int
    priority: int = Field(ge=1, le=10, default=5)
    safety_notes: Optional[List[str]] = None
    special_tools_required: Optional[List[str]] = None
    
    class Config:
        use_enum_values = True


class GateOperation(BaseModel):
    """Gate operation details"""
    gate_id: str
    gate_name: str
    location: Dict[str, float]
    current_state: str
    target_state: str
    operation_type: str
    physical_description: str
    reference_photos: Optional[List[str]] = None


class TeamAssignment(BaseModel):
    """Team assignment for operations"""
    team_id: str
    team_name: str
    assigned_date: date
    operations: List[str] = Field(description="List of operation IDs")
    estimated_duration_hours: float
    route_distance_km: float
    start_location: Dict[str, float]
    end_location: Dict[str, float]


class OperationReport(BaseModel):
    """Report submitted by field team"""
    operation_id: str
    completed_at: datetime
    operator_id: str
    team_id: str
    actual_opening_m: float
    photos_taken: int
    issues_encountered: Optional[List[str]] = None
    notes: Optional[str] = None
    weather_conditions: Optional[str] = None
    next_gate_eta_minutes: Optional[int] = None
    
    @validator('actual_opening_m')
    def validate_opening(cls, v):
        if v < 0:
            raise ValueError("Opening cannot be negative")
        return round(v, 2)


class TeamLocation(BaseModel):
    """Current team location update"""
    team_id: str
    timestamp: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float
    speed_kmh: Optional[float] = None
    heading_degrees: Optional[float] = None
    battery_level: Optional[int] = Field(None, ge=0, le=100)
    status: TeamStatus


class PhotoUpload(BaseModel):
    """Photo upload metadata"""
    operation_id: str
    filename: str
    content_type: str
    size: int
    caption: Optional[str] = None
    latitude: float
    longitude: float
    timestamp: datetime
    compass_heading: Optional[float] = None


class RouteOptimization(BaseModel):
    """Optimized route for field team"""
    team_id: str
    date: date
    waypoints: List[Dict[str, Any]]
    total_distance_km: float
    estimated_duration_hours: float
    optimal_order: List[str] = Field(description="Ordered list of operation IDs")
    turn_by_turn: Optional[List[Dict[str, str]]] = None


class OfflineDataPackage(BaseModel):
    """Data package for offline mobile app use"""
    sync_token: str
    generated_at: datetime
    valid_until: datetime
    team_id: str
    schedules: List[Dict[str, Any]]
    gate_locations: Dict[str, Dict[str, float]]
    gate_photos: Dict[str, List[str]]
    physical_markers: Dict[str, str]
    emergency_contacts: List[Dict[str, str]]


class SyncData(BaseModel):
    """Data synchronization from mobile app"""
    sync_token: str
    device_id: str
    team_id: str
    reports: List[OperationReport]
    photos: List[PhotoUpload]
    locations: List[TeamLocation]
    offline_duration_hours: float
    data_collected_at: List[datetime]