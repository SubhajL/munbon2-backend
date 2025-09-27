"""
Pydantic schemas for request/response validation
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List, Any
from datetime import datetime, date
from uuid import UUID
from enum import Enum


class OptimizationObjective(str, Enum):
    """Optimization objectives"""
    water_efficiency = "water_efficiency"
    fairness = "fairness"
    energy_minimal = "energy_minimal"
    multi_objective = "multi_objective"


class SimulationStatus(str, Enum):
    """Simulation run status"""
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class GateOperationType(str, Enum):
    """Gate operation types"""
    automatic = "automatic"
    manual = "manual"
    maintenance = "maintenance"


# Request Schemas
class ScenarioCreate(BaseModel):
    """Create a new simulation scenario"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    base_date: date
    duration_days: int = Field(..., ge=1, le=365)
    time_step_minutes: int = Field(default=60, ge=15, le=1440)
    optimization_objective: OptimizationObjective = OptimizationObjective.multi_objective
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator("time_step_minutes")
    def validate_time_step(cls, v):
        if 1440 % v != 0:
            raise ValueError("Time step must evenly divide into 24 hours")
        return v


class ScenarioUpdate(BaseModel):
    """Update scenario parameters"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SectionDemandCreate(BaseModel):
    """Define section-specific demand parameters"""
    section_id: str = Field(..., min_length=1, max_length=50)
    week_number: int = Field(..., ge=1, le=53)
    base_demand_m3: Optional[float] = Field(None, ge=0)
    weather_adjustment_factor: float = Field(default=1.0, ge=0.1, le=2.0)
    priority_override: Optional[float] = Field(None, ge=0, le=10)
    min_delivery_m3: Optional[float] = Field(None, ge=0)
    max_delivery_m3: Optional[float] = Field(None, ge=0)
    delivery_window_hours: int = Field(default=168, ge=1, le=168)
    
    @validator("max_delivery_m3")
    def validate_max_delivery(cls, v, values):
        if v is not None and "min_delivery_m3" in values and values["min_delivery_m3"] is not None:
            if v < values["min_delivery_m3"]:
                raise ValueError("max_delivery_m3 must be greater than min_delivery_m3")
        return v


class SimulationRunCreate(BaseModel):
    """Start a new simulation run"""
    scenario_id: UUID
    start_from_time: Optional[datetime] = None  # Resume from specific time


class GateOperationSchedule(BaseModel):
    """Schedule a gate operation"""
    gate_id: str = Field(..., min_length=1, max_length=50)
    scheduled_time: datetime
    target_opening_m: float = Field(..., ge=0, le=10)
    operation_type: GateOperationType = GateOperationType.automatic
    priority: str = Field(default="normal", pattern="^(low|normal|high|emergency)$")


# Response Schemas
class ScenarioResponse(BaseModel):
    """Scenario details response"""
    scenario_id: UUID
    name: str
    description: Optional[str]
    base_date: date
    duration_days: int
    time_step_minutes: int
    optimization_objective: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]
    
    class Config:
        orm_mode = True


class SimulationRunResponse(BaseModel):
    """Simulation run details"""
    run_id: UUID
    scenario_id: UUID
    status: SimulationStatus
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    current_simulation_time: Optional[datetime]
    progress_percent: float
    error_message: Optional[str]
    statistics: Dict[str, Any]
    created_at: datetime
    
    class Config:
        orm_mode = True


class SimulationStateResponse(BaseModel):
    """Simulation state at a point in time"""
    state_id: int
    simulation_time: datetime
    time_step: int
    water_levels: Dict[str, float]
    gate_positions: Dict[str, float]
    flow_rates: Dict[str, float]
    total_demand_m3: Optional[float]
    total_supply_m3: Optional[float]
    total_delivered_m3: Optional[float]
    system_efficiency: Optional[float]
    
    class Config:
        orm_mode = True


class OptimizationResultResponse(BaseModel):
    """Optimization results"""
    result_id: int
    optimization_time: datetime
    objective_function: str
    water_efficiency_score: Optional[float]
    fairness_index: Optional[float]
    energy_usage_kwh: Optional[float]
    computational_time_ms: Optional[int]
    iterations: Optional[int]
    convergence_achieved: bool
    gate_schedule: Dict[str, Any]
    section_allocations: Dict[str, Any]
    
    class Config:
        orm_mode = True


class AnalysisResultResponse(BaseModel):
    """Analysis results from simulation"""
    analysis_id: int
    analysis_type: str
    avg_delivery_efficiency: Optional[float]
    water_shortage_events: int
    excess_water_events: int
    unmet_demand_m3: Optional[float]
    section_performance: Optional[Dict[str, Any]]
    temporal_analysis: Optional[Dict[str, Any]]
    recommendations: Optional[List[str]]
    
    class Config:
        orm_mode = True


class SimulationSummary(BaseModel):
    """Summary of simulation results"""
    run_id: UUID
    scenario_name: str
    status: SimulationStatus
    duration_hours: float
    total_water_demand_m3: float
    total_water_delivered_m3: float
    overall_efficiency: float
    optimization_score: float
    key_findings: List[str]
    
    
class PaginatedResponse(BaseModel):
    """Paginated list response"""
    items: List[Any]
    total: int
    page: int
    per_page: int
    pages: int