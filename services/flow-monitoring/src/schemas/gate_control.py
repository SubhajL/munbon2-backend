"""
Pydantic schemas for gate control API
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


class GateMode(str, Enum):
    """Gate operational modes"""
    AUTOMATED = "automated"
    MANUAL = "manual"
    HYBRID = "hybrid"
    MAINTENANCE = "maintenance"
    FAILED = "failed"


class GateType(str, Enum):
    """Physical gate types"""
    UNDERSHOT = "undershot"
    OVERSHOT = "overshot"
    RADIAL = "radial"
    VERTICAL = "vertical"


class ControlStatus(str, Enum):
    """Gate control status"""
    ACTIVE = "active"
    STANDBY = "standby"
    TRANSITIONING = "transitioning"
    FAULT = "fault"
    OFFLINE = "offline"


class GateState(BaseModel):
    """Current state of a gate"""
    gate_id: str
    mode: GateMode
    control_status: ControlStatus
    opening_percentage: float = Field(ge=0, le=100, description="Gate opening 0-100%")
    target_opening: Optional[float] = Field(None, ge=0, le=100)
    flow_rate: Optional[float] = Field(None, description="Current flow rate in m³/s")
    upstream_level: Optional[float] = Field(None, description="Upstream water level in meters")
    downstream_level: Optional[float] = Field(None, description="Downstream water level in meters")
    last_updated: datetime
    last_command_time: Optional[datetime] = None
    error_state: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class GateStateResponse(GateState):
    """Extended gate state for API responses"""
    gate_type: GateType
    location: Dict[str, Any] = Field(description="Gate location information")
    calibration_params: Optional[Dict[str, float]] = None
    operational_constraints: Optional[Dict[str, Any]] = None
    maintenance_status: Optional[Dict[str, Any]] = None


class ManualGateCommand(BaseModel):
    """Command for manual gate operation"""
    opening_percentage: float = Field(ge=0, le=100, description="Target gate opening")
    operator_id: str = Field(description="ID of field operator")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = Field(None, description="Operator notes")
    estimated_duration: Optional[int] = Field(None, description="Estimated time to reach target (minutes)")
    
    @validator('opening_percentage')
    def validate_opening(cls, v):
        # Round to nearest 5% for manual operations
        return round(v / 5) * 5


class AutomatedGateCommand(BaseModel):
    """Command for automated gate operation"""
    gate_id: str
    target_opening: float = Field(ge=0, le=100)
    target_flow: Optional[float] = Field(None, description="Target flow rate in m³/s")
    control_mode: str = Field(default="position", description="Control mode: position or flow")
    ramp_time: Optional[int] = Field(None, description="Time to reach target (seconds)")
    priority: int = Field(default=5, ge=1, le=10, description="Command priority 1-10")


class GateTransitionRequest(BaseModel):
    """Request for gate mode transition"""
    gate_id: str
    target_mode: GateMode
    reason: str = Field(description="Reason for transition")
    force: bool = Field(default=False, description="Force transition even with warnings")
    transition_time: Optional[int] = Field(None, description="Transition duration in seconds")
    operator_id: Optional[str] = None


class GateTransitionValidation(BaseModel):
    """Validation result for mode transition"""
    is_valid: bool
    current_mode: GateMode
    target_mode: GateMode
    reason: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    estimated_impact: Optional[Dict[str, Any]] = None


class ManualInstruction(BaseModel):
    """Instruction for manual gate operation"""
    gate_id: str
    current_opening: float
    target_opening: float
    priority: bool = Field(default=False)
    reason: str
    estimated_flow_change: Optional[float] = None
    coordination_notes: Optional[str] = None
    safety_checks: List[str] = Field(default_factory=list)


class SynchronizationStatus(BaseModel):
    """Status of automated/manual synchronization"""
    is_synchronized: bool
    last_sync_time: datetime
    automated_gates: List[str]
    manual_gates: List[str]
    hybrid_gates: List[str]
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    sync_quality: float = Field(ge=0, le=1, description="Synchronization quality 0-1")


class GateBatchCommand(BaseModel):
    """Command for batch gate operations"""
    commands: List[Dict[str, Any]]
    coordination_mode: str = Field(default="sequential", description="sequential or parallel")
    total_flow_target: Optional[float] = None
    maintain_balance: bool = Field(default=True)
    safety_checks: bool = Field(default=True)


class GateLocation(BaseModel):
    """Gate geographic location"""
    lat: float = Field(description="Latitude")
    lon: float = Field(description="Longitude")


class GateConfigResponse(BaseModel):
    """Complete gate configuration information"""
    gate_id: str
    name: str
    type: str = Field(description="automated or manual")
    location: GateLocation
    zone: int
    width_m: float
    max_opening_m: float
    max_flow_m3s: float
    calibration: Dict[str, float]
    scada_id: Optional[str] = None
    physical_markers: Optional[str] = None
    fallback_manual: bool = False
    manual_operation: Optional[Dict[str, Any]] = None