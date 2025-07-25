"""
Data models for Gravity Flow Optimizer
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

class FlowRegime(str, Enum):
    SUBCRITICAL = "subcritical"
    CRITICAL = "critical"
    SUPERCRITICAL = "supercritical"

class GateType(str, Enum):
    AUTOMATED = "automated"
    MANUAL = "manual"

class DeliveryPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class TargetDelivery(BaseModel):
    section_id: str
    zone: int
    required_flow_m3s: float
    required_volume_m3: float
    target_elevation_m: float
    priority: DeliveryPriority
    delivery_window_hours: float
    crop_type: str
    growth_stage: str

class GateState(BaseModel):
    gate_id: str
    type: GateType
    current_opening_m: float
    max_opening_m: float
    width_m: float
    sill_elevation_m: float
    calibration_k1: float = 0.61
    calibration_k2: float = -0.12

class NetworkNode(BaseModel):
    node_id: str
    elevation_m: float
    water_level_m: Optional[float] = None
    connected_gates: List[str]

class CanalSection(BaseModel):
    canal_id: str
    upstream_node: str
    downstream_node: str
    length_m: float
    bed_slope: float
    bottom_width_m: float
    side_slope: float
    manning_n: float = 0.025
    max_depth_m: float

class OptimizationConstraints(BaseModel):
    min_depth_m: float = 0.3
    max_velocity_ms: float = 2.0
    min_velocity_ms: float = 0.3
    max_gate_change_rate: float = 0.1  # m/min
    preserve_energy_factor: float = 0.95
    max_iterations: int = 1000
    convergence_tolerance: float = 0.001

class GravityOptimizationRequest(BaseModel):
    target_deliveries: List[TargetDelivery]
    current_gate_states: Dict[str, GateState]
    network_topology: Dict[str, Any]
    source_elevation: float = 221.0
    constraints: OptimizationConstraints = Field(default_factory=OptimizationConstraints)

class OptimalGateSetting(BaseModel):
    gate_id: str
    optimal_opening_m: float
    flow_m3s: float
    head_loss_m: float
    upstream_level_m: float
    downstream_level_m: float
    velocity_ms: float
    froude_number: float

class EnergyPoint(BaseModel):
    location: str
    distance_m: float
    elevation_m: float
    water_depth_m: float
    pressure_head_m: float
    velocity_head_m: float
    total_energy_m: float
    specific_energy_m: float

class GravityOptimizationResponse(BaseModel):
    optimal_gate_settings: Dict[str, OptimalGateSetting]
    energy_profiles: Dict[str, List[EnergyPoint]]
    total_head_loss: float
    delivery_times: Dict[str, float]  # section_id -> hours
    feasibility_warnings: List[str]
    optimization_metrics: Dict[str, Any]

class EnergyProfileResponse(BaseModel):
    path: str
    nodes: List[str]
    energy_profile: List[EnergyPoint]
    hydraulic_grade_line: List[float]
    total_head_loss: float
    critical_points: List[str]
    minimum_pressure_head: float

class FeasibilityCheckRequest(BaseModel):
    source_node: str
    target_section: str
    target_elevation: float
    required_flow_m3s: float
    path_nodes: List[str]
    check_depth_requirements: bool = True

class FeasibilityCheckResponse(BaseModel):
    feasible: bool
    required_upstream_level: float
    available_head: float
    total_losses: float
    minimum_depths_met: bool
    critical_sections: List[str]
    recommendations: List[str]

class FrictionLossResponse(BaseModel):
    canal_id: str
    flow_m3s: float
    friction_loss_m: float
    friction_slope: float
    velocity_ms: float
    hydraulic_radius_m: float
    reynolds_number: float
    flow_regime: FlowRegime
    manning_n: float
    length_m: float

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp: datetime

class HydraulicState(BaseModel):
    node_id: str
    water_level_m: float
    flow_m3s: float
    velocity_ms: float
    depth_m: float
    froude_number: float
    specific_energy_m: float

class OptimizationResult(BaseModel):
    gate_settings: Dict[str, OptimalGateSetting]
    total_head_loss: float
    delivery_times: Dict[str, float]
    iterations: int
    convergence_error: float
    computation_time_ms: int

class ElevationCheck(BaseModel):
    feasible: bool
    available_head: float
    required_head: float
    total_losses: float
    loss_breakdown: Dict[str, float]

class DepthCheck(BaseModel):
    feasible: bool
    all_depths_met: bool
    critical_sections: List[str]
    depth_violations: Dict[str, float]

class CanalCharacteristics(BaseModel):
    canal_id: str
    length_m: float
    bed_slope: float
    bottom_width_m: float
    side_slope: float
    manning_n: float
    current_flow_m3s: float
    current_depth_m: float

class FrictionLossResult(BaseModel):
    friction_loss: float
    friction_slope: float
    velocity: float
    hydraulic_radius: float
    reynolds_number: float
    flow_regime: FlowRegime

class PathProfile(BaseModel):
    energy_points: List[EnergyPoint]
    hgl_points: List[float]
    total_head_loss: float
    critical_points: List[str]
    min_pressure_head: float