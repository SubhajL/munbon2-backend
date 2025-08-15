from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum


class OptimizationObjective(str, Enum):
    MINIMIZE_TRAVEL_TIME = "minimize_travel_time"
    MAXIMIZE_EFFICIENCY = "maximize_efficiency"
    MINIMIZE_ENERGY_LOSS = "minimize_energy_loss"
    BALANCED = "balanced"


class ZoneDeliveryRequest(BaseModel):
    zone_id: str
    required_volume: float = Field(..., description="Required water volume in m³")
    required_flow_rate: float = Field(..., description="Required flow rate in m³/s")
    priority: int = Field(1, description="Priority level (1=highest)")
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    min_pressure_head: float = Field(0.5, description="Minimum pressure head in meters")


class GateSetting(BaseModel):
    gate_id: str
    opening_ratio: float = Field(..., ge=0, le=1, description="Gate opening ratio (0-1)")
    timestamp: datetime
    flow_rate: float = Field(..., description="Expected flow rate through gate in m³/s")
    upstream_head: float = Field(..., description="Upstream water head in meters")
    downstream_head: float = Field(..., description="Downstream water head in meters")


class DeliverySequence(BaseModel):
    sequence_id: str
    zone_id: str
    order: int
    start_time: datetime
    end_time: datetime
    gate_settings: List[GateSetting]
    expected_travel_time: float = Field(..., description="Expected travel time in minutes")
    total_head_loss: float = Field(..., description="Total head loss in meters")


class ElevationFeasibility(BaseModel):
    zone_id: str
    is_feasible: bool
    min_required_source_level: float = Field(..., description="Minimum required source water level in MSL meters")
    available_head: float = Field(..., description="Available head at zone in meters")
    total_head_loss: float = Field(..., description="Total head loss from source in meters")
    critical_sections: List[str] = Field([], description="Channel sections with minimal head")
    recommended_flow_rate: float = Field(..., description="Recommended flow rate in m³/s")
    warnings: List[str] = []


class FlowSplitOptimization(BaseModel):
    optimization_id: str
    timestamp: datetime
    objective: OptimizationObjective
    total_inflow: float = Field(..., description="Total available inflow in m³/s")
    zone_allocations: Dict[str, float] = Field(..., description="Flow allocation per zone in m³/s")
    gate_settings: List[GateSetting]
    efficiency: float = Field(..., description="Overall efficiency (0-1)")
    convergence_iterations: int
    optimization_time: float = Field(..., description="Computation time in seconds")


class EnergyRecoveryPotential(BaseModel):
    location_id: str
    channel_id: str
    available_head: float = Field(..., description="Available head in meters")
    flow_rate: float = Field(..., description="Average flow rate in m³/s")
    potential_power: float = Field(..., description="Potential power generation in kW")
    annual_energy: float = Field(..., description="Estimated annual energy in MWh")
    installation_feasibility: str
    estimated_cost: Optional[float] = None
    payback_period: Optional[float] = None


class ContingencyPlan(BaseModel):
    plan_id: str
    trigger_condition: str
    affected_zones: List[str]
    alternative_routes: List[Dict[str, any]]
    gate_adjustments: List[GateSetting]
    expected_performance: float = Field(..., description="Expected delivery efficiency (0-1)")
    head_loss_increase: float = Field(..., description="Additional head loss in meters")


class OptimizationResult(BaseModel):
    request_id: str
    timestamp: datetime
    objective: OptimizationObjective
    zone_requests: List[ZoneDeliveryRequest]
    feasibility_results: List[ElevationFeasibility]
    delivery_sequence: List[DeliverySequence]
    flow_splits: FlowSplitOptimization
    energy_recovery: Optional[List[EnergyRecoveryPotential]] = None
    contingency_plans: Optional[List[ContingencyPlan]] = None
    total_delivery_time: float = Field(..., description="Total delivery time in hours")
    overall_efficiency: float = Field(..., description="Overall system efficiency (0-1)")
    warnings: List[str] = []
    
    
class OptimizationConstraints(BaseModel):
    max_velocity: float = Field(2.0, description="Maximum flow velocity in m/s")
    min_velocity: float = Field(0.3, description="Minimum flow velocity in m/s")
    min_depth: float = Field(0.3, description="Minimum flow depth in meters")
    max_gate_changes_per_hour: int = Field(10, description="Maximum gate adjustments per hour")
    min_delivery_efficiency: float = Field(0.7, description="Minimum acceptable delivery efficiency")
    max_travel_time_hours: float = Field(24, description="Maximum acceptable travel time")