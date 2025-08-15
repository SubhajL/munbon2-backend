"""
Adaptation schemas for the scheduler service.

These schemas define real-time adaptation requests and responses,
including gate failures, weather changes, and dynamic rescheduling.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, validator, root_validator


class AdaptationType(str, Enum):
    """Types of schedule adaptations"""
    GATE_FAILURE = "gate_failure"
    WEATHER_CHANGE = "weather_change"
    DEMAND_CHANGE = "demand_change"
    TEAM_UNAVAILABLE = "team_unavailable"
    EMERGENCY_REQUEST = "emergency_request"
    FLOW_CONSTRAINT = "flow_constraint"
    SYSTEM_OPTIMIZATION = "system_optimization"


class FailureType(str, Enum):
    """Types of gate failures"""
    MECHANICAL = "mechanical"
    ELECTRICAL = "electrical"
    BLOCKAGE = "blockage"
    VANDALISM = "vandalism"
    STRUCTURAL = "structural"
    SENSOR_FAILURE = "sensor_failure"
    COMMUNICATION = "communication"
    UNKNOWN = "unknown"


class AdaptationStrategy(str, Enum):
    """Strategies for handling adaptations"""
    REROUTE_FLOW = "reroute_flow"
    DELAY_OPERATIONS = "delay_operations"
    PARTIAL_DELIVERY = "partial_delivery"
    EMERGENCY_OVERRIDE = "emergency_override"
    REDISTRIBUTE_DEMAND = "redistribute_demand"
    ACTIVATE_BACKUP = "activate_backup"
    MANUAL_INTERVENTION = "manual_intervention"


class WeatherChangeType(str, Enum):
    """Types of weather changes"""
    RAINFALL = "rainfall"
    DROUGHT = "drought"
    HIGH_TEMPERATURE = "high_temperature"
    STORM = "storm"
    FLOODING = "flooding"
    FORECAST_UPDATE = "forecast_update"


class DemandUrgency(str, Enum):
    """Urgency levels for demand changes"""
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class GateFailureRequest(BaseModel):
    """Request to handle gate failure"""
    schedule_id: UUID
    gate_id: str
    failure_type: FailureType
    failure_description: str
    detected_at: datetime
    
    # Impact assessment
    estimated_repair_hours: float = Field(..., ge=0)
    can_partially_operate: bool = False
    partial_capacity_percent: Optional[float] = Field(None, ge=0, le=100)
    
    # Affected operations
    affected_operation_ids: List[UUID] = Field(default_factory=list)
    downstream_gates: List[str] = Field(default_factory=list)
    affected_zones: List[str] = Field(default_factory=list)
    
    # Urgency
    blocks_critical_path: bool = False
    affected_demand_m3: Optional[float] = Field(None, ge=0)
    
    @validator('partial_capacity_percent')
    def validate_partial_capacity(cls, v, values):
        if values.get('can_partially_operate') and v is None:
            raise ValueError("partial_capacity_percent required when can_partially_operate is True")
        return v


class WeatherChangeRequest(BaseModel):
    """Request to adapt to weather changes"""
    schedule_id: UUID
    change_type: WeatherChangeType
    detected_at: datetime
    
    # Weather data
    rainfall_mm: Optional[float] = Field(None, ge=0)
    temperature_celsius: Optional[float] = None
    humidity_percent: Optional[float] = Field(None, ge=0, le=100)
    evapotranspiration_mm: Optional[float] = Field(None, ge=0)
    
    # Forecast
    forecast_hours: int = Field(24, ge=1, le=168)
    expected_rainfall_mm: Optional[float] = Field(None, ge=0)
    storm_probability_percent: Optional[float] = Field(None, ge=0, le=100)
    
    # Impact zones
    affected_zones: List[str]
    affected_crops: Optional[List[str]] = None
    
    # Recommendations from weather service
    recommended_adjustment_percent: Optional[float] = Field(None, ge=-100, le=100)
    
    @root_validator
    def validate_weather_data(cls, values):
        change_type = values.get('change_type')
        if change_type == WeatherChangeType.RAINFALL and values.get('rainfall_mm') is None:
            raise ValueError("rainfall_mm required for RAINFALL change type")
        return values


class DemandChangeRequest(BaseModel):
    """Request to handle demand changes"""
    schedule_id: UUID
    zone_id: str
    plot_ids: List[str]
    change_type: str = Field(..., description="increase, decrease, emergency")
    urgency: DemandUrgency
    
    # Demand change
    original_demand_m3: float = Field(..., ge=0)
    new_demand_m3: float = Field(..., ge=0)
    change_percentage: Optional[float] = None
    
    # Timing
    effective_from: datetime
    effective_until: Optional[datetime] = None
    
    # Reason
    reason: str
    requestor: str
    authorization_code: Optional[str] = None
    
    # Constraints
    must_complete_by: Optional[datetime] = None
    can_split_delivery: bool = True
    minimum_delivery_m3: Optional[float] = Field(None, ge=0)
    
    @validator('change_percentage', always=True)
    def calculate_change_percentage(cls, v, values):
        if v is None:
            original = values.get('original_demand_m3', 0)
            new = values.get('new_demand_m3', 0)
            if original > 0:
                return ((new - original) / original) * 100
        return v


class TeamUnavailableRequest(BaseModel):
    """Request to handle team unavailability"""
    schedule_id: UUID
    team_id: UUID
    unavailable_from: datetime
    unavailable_until: Optional[datetime] = None
    reason: str
    
    # Operations affected
    affected_operation_ids: List[UUID]
    operations_in_progress: List[UUID] = Field(default_factory=list)
    
    # Alternatives
    suggested_replacement_teams: List[UUID] = Field(default_factory=list)
    can_delay_operations: bool = True
    max_delay_hours: Optional[float] = Field(None, ge=0)


class ReoptimizationRequest(BaseModel):
    """Request to reoptimize schedule"""
    schedule_id: UUID
    from_date: date
    to_date: Optional[date] = None
    
    # Trigger
    trigger_type: AdaptationType
    trigger_description: str
    
    # Constraints for reoptimization
    constraints: Dict[str, Any] = Field(default_factory=dict)
    
    # Objectives (priority order)
    optimization_objectives: List[str] = Field(
        default_factory=lambda: ["minimize_changes", "satisfy_demands", "minimize_travel"]
    )
    
    # Options
    allow_team_overtime: bool = False
    allow_partial_delivery: bool = True
    allow_demand_postponement: bool = False
    preserve_completed_operations: bool = True
    
    # Performance
    max_computation_seconds: int = Field(30, ge=5, le=300)
    acceptable_solution_quality: float = Field(0.95, ge=0.5, le=1.0)


class AdaptationResponse(BaseModel):
    """Response from adaptation request"""
    adaptation_id: UUID
    request_type: AdaptationType
    status: str = Field(..., description="accepted, processing, completed, failed")
    
    # Strategy
    selected_strategy: AdaptationStrategy
    confidence_score: float = Field(..., ge=0, le=1)
    
    # Changes made
    operations_added: int = 0
    operations_modified: int = 0
    operations_cancelled: int = 0
    operations_rescheduled: int = 0
    
    # Impact
    affected_teams: List[str] = Field(default_factory=list)
    affected_gates: List[str] = Field(default_factory=list)
    affected_zones: List[str] = Field(default_factory=list)
    
    # Water delivery impact
    original_delivery_m3: float
    adapted_delivery_m3: float
    delivery_satisfaction_percent: float = Field(..., ge=0, le=100)
    
    # Timeline
    requested_at: datetime
    processing_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None
    
    # Details
    adaptation_details: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class AdaptationSummary(BaseModel):
    """Summary of adaptations for a schedule"""
    schedule_id: UUID
    total_adaptations: int
    
    # By type
    adaptations_by_type: Dict[str, int]
    
    # By strategy
    strategies_used: Dict[str, int]
    
    # Performance
    average_processing_time_seconds: float
    success_rate: float = Field(..., ge=0, le=100)
    
    # Impact
    total_operations_affected: int
    total_water_impact_m3: float
    schedule_stability_score: float = Field(..., ge=0, le=100)
    
    # Recent adaptations
    recent_adaptations: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            UUID: lambda v: str(v),
        }


class ContingencyPlan(BaseModel):
    """Pre-defined contingency plan"""
    plan_id: UUID
    name: str
    description: str
    trigger_conditions: List[Dict[str, Any]]
    
    # Actions
    automatic_actions: List[Dict[str, Any]]
    manual_actions: List[Dict[str, Any]]
    notification_list: List[str]
    
    # Activation
    auto_activate: bool = False
    requires_approval: bool = True
    approval_roles: List[str] = Field(default_factory=list)
    
    # History
    last_activated: Optional[datetime] = None
    activation_count: int = 0
    average_resolution_time_hours: Optional[float] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            UUID: lambda v: str(v),
        }


class AdaptationMetrics(BaseModel):
    """Metrics for adaptation performance"""
    period_start: date
    period_end: date
    
    # Volume
    total_adaptations: int
    adaptations_by_type: Dict[str, int]
    
    # Performance
    average_response_time_seconds: float
    success_rate: float = Field(..., ge=0, le=100)
    auto_resolution_rate: float = Field(..., ge=0, le=100)
    
    # Impact
    average_operations_affected: float
    total_water_impact_m3: float
    demand_satisfaction_maintained: float = Field(..., ge=0, le=100)
    
    # Patterns
    peak_adaptation_hour: int = Field(..., ge=0, le=23)
    most_common_trigger: str
    most_effective_strategy: str
    
    # Improvements
    adaptation_time_trend: List[float] = Field(..., description="Daily average times")
    learning_score: float = Field(..., ge=0, le=100, description="System learning effectiveness")