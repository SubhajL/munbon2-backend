"""
Team schemas for the scheduler service.

These schemas define the data structures for field teams,
including availability, location tracking, and instructions.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date, time
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, validator, root_validator


class TeamStatus(str, Enum):
    """Team availability status"""
    AVAILABLE = "available"
    BUSY = "busy"
    ON_BREAK = "on_break"
    OFF_DUTY = "off_duty"
    EMERGENCY = "emergency"


class TeamCapability(str, Enum):
    """Team capabilities/skills"""
    GATE_OPERATION = "gate_operation"
    PUMP_OPERATION = "pump_operation"
    MAINTENANCE = "maintenance"
    INSPECTION = "inspection"
    EMERGENCY_RESPONSE = "emergency_response"
    SCADA_OPERATION = "scada_operation"


class VehicleType(str, Enum):
    """Types of vehicles for transportation"""
    PICKUP = "pickup"
    MOTORCYCLE = "motorcycle"
    BOAT = "boat"
    BICYCLE = "bicycle"
    ON_FOOT = "on_foot"


class TeamLocation(BaseModel):
    """Real-time team location"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: float = Field(..., ge=0, description="GPS accuracy in meters")
    timestamp: datetime
    speed: Optional[float] = Field(None, ge=0, description="Speed in km/h")
    heading: Optional[float] = Field(None, ge=0, le=360, description="Direction in degrees")
    altitude: Optional[float] = Field(None, description="Altitude in meters")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class TeamMember(BaseModel):
    """Individual team member info"""
    id: str
    name: str
    role: str = Field(..., description="Role in team (e.g., leader, operator)")
    phone: Optional[str] = None
    capabilities: List[TeamCapability] = Field(default_factory=list)
    years_experience: Optional[int] = Field(None, ge=0)
    certifications: List[str] = Field(default_factory=list)
    emergency_contact: Optional[str] = None


class TeamBase(BaseModel):
    """Base team information"""
    team_code: str = Field(..., regex="^TEAM-[A-Z0-9]+$", description="Unique team code")
    name: str = Field(..., max_length=100)
    base_location: str = Field(..., description="Home base location")
    base_latitude: float = Field(..., ge=-90, le=90)
    base_longitude: float = Field(..., ge=-180, le=180)
    
    # Contact info
    primary_phone: str
    secondary_phone: Optional[str] = None
    radio_channel: Optional[str] = None
    
    # Capabilities
    capabilities: List[TeamCapability]
    max_operations_per_day: int = Field(8, ge=1, le=20)
    operating_hours_start: time = Field(time(6, 0), description="Daily start time")
    operating_hours_end: time = Field(time(18, 0), description="Daily end time")
    
    # Transportation
    vehicle_type: VehicleType
    vehicle_id: Optional[str] = None
    average_speed_kmh: float = Field(..., ge=1, le=120)
    
    # Areas of responsibility
    assigned_zones: List[str] = Field(default_factory=list, description="Zone IDs")
    max_travel_radius_km: float = Field(50, ge=1, le=200)


class TeamCreate(TeamBase):
    """Schema for creating a team"""
    members: List[TeamMember]
    active: bool = True
    notes: Optional[str] = None
    
    @validator('members')
    def validate_members(cls, v):
        if not v:
            raise ValueError("Team must have at least one member")
        
        # Check for team leader
        leaders = [m for m in v if "leader" in m.role.lower()]
        if not leaders:
            raise ValueError("Team must have at least one leader")
        
        return v


class TeamUpdate(BaseModel):
    """Schema for updating team info"""
    name: Optional[str] = Field(None, max_length=100)
    primary_phone: Optional[str] = None
    secondary_phone: Optional[str] = None
    capabilities: Optional[List[TeamCapability]] = None
    max_operations_per_day: Optional[int] = Field(None, ge=1, le=20)
    operating_hours_start: Optional[time] = None
    operating_hours_end: Optional[time] = None
    vehicle_type: Optional[VehicleType] = None
    average_speed_kmh: Optional[float] = Field(None, ge=1, le=120)
    assigned_zones: Optional[List[str]] = None
    active: Optional[bool] = None
    
    class Config:
        extra = "forbid"


class TeamResponse(TeamBase):
    """Team response with full details"""
    id: UUID
    members: List[TeamMember]
    status: TeamStatus = TeamStatus.AVAILABLE
    current_location: Optional[TeamLocation] = None
    active: bool = True
    
    # Statistics
    operations_today: int = 0
    operations_this_week: int = 0
    average_completion_time: Optional[float] = None
    on_time_rate: Optional[float] = None
    
    # Current assignment
    current_operation_id: Optional[UUID] = None
    next_operation_id: Optional[UUID] = None
    
    # Metadata
    created_at: datetime
    updated_at: Optional[datetime] = None
    notes: Optional[str] = None
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            time: lambda v: v.isoformat(),
        }


class TeamSummary(BaseModel):
    """Simplified team summary for lists"""
    id: UUID
    team_code: str
    name: str
    status: TeamStatus
    member_count: int
    current_location: Optional[Dict[str, float]] = None
    operations_today: int
    vehicle_type: VehicleType
    capabilities: List[TeamCapability]
    
    class Config:
        json_encoders = {
            UUID: lambda v: str(v),
        }


class TeamAvailability(BaseModel):
    """Team availability for scheduling"""
    team_id: UUID
    date: date
    available: bool
    reason: Optional[str] = Field(None, description="Reason if not available")
    available_hours: Optional[List[Dict[str, time]]] = Field(
        None, description="Available time slots if partially available"
    )
    max_operations: Optional[int] = Field(None, description="Override max operations for this date")
    
    @root_validator
    def validate_availability(cls, values):
        if not values.get('available') and not values.get('reason'):
            raise ValueError("Reason required when team is not available")
        return values


class TeamInstructions(BaseModel):
    """Daily instructions for a team"""
    team_id: UUID
    team_code: str
    date: date
    operations: List[Dict[str, Any]] = Field(..., description="Ordered list of operations")
    total_operations: int
    estimated_duration_hours: float
    total_travel_km: float
    
    # Route information
    start_location: Dict[str, Any]
    end_location: Dict[str, Any]
    route_waypoints: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Instructions
    general_notes: Optional[str] = None
    safety_warnings: List[str] = Field(default_factory=list)
    emergency_contacts: List[Dict[str, str]] = Field(default_factory=list)
    
    # Resources
    required_tools: List[str] = Field(default_factory=list)
    spare_parts: List[str] = Field(default_factory=list)
    
    # Offline data
    offline_maps_url: Optional[str] = None
    offline_data_version: Optional[str] = None
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class TeamPerformance(BaseModel):
    """Team performance metrics"""
    team_id: UUID
    period_start: date
    period_end: date
    
    # Operation metrics
    total_operations: int
    completed_operations: int
    failed_operations: int
    completion_rate: float = Field(..., ge=0, le=100)
    
    # Time metrics
    average_operation_time_minutes: float
    total_overtime_hours: float
    on_time_rate: float = Field(..., ge=0, le=100)
    
    # Travel metrics
    total_distance_km: float
    fuel_efficiency_km_per_liter: Optional[float] = None
    
    # Quality metrics
    verification_compliance_rate: float = Field(..., ge=0, le=100)
    safety_incidents: int = 0
    customer_complaints: int = 0
    
    # Ranking
    efficiency_score: float = Field(..., ge=0, le=100)
    rank_in_zone: Optional[int] = None
    rank_overall: Optional[int] = None
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class TeamLocationUpdate(BaseModel):
    """Location update from field team"""
    team_id: UUID
    location: TeamLocation
    status: TeamStatus
    current_operation_id: Optional[UUID] = None
    eta_next_location: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=200)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }