from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID
from enum import Enum


class AnomalySeverity(str, Enum):
    """Anomaly severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AnomalyType(str, Enum):
    """Types of flow anomalies"""
    SENSOR_MALFUNCTION = "sensor_malfunction"
    ZERO_FLOW = "zero_flow"
    NEGATIVE_FLOW = "negative_flow"
    EXCESSIVE_FLOW = "excessive_flow"
    SUDDEN_CHANGE = "sudden_change"
    DATA_GAP = "data_gap"
    LEAK_DETECTED = "leak_detected"
    BLOCKAGE_DETECTED = "blockage_detected"
    QUALITY_DEGRADATION = "quality_degradation"


class WaterBalance(BaseModel):
    """Water balance calculation results"""
    segment_id: UUID
    segment_name: str
    time: datetime
    time_period: str = Field(..., description="Time period for balance calculation (e.g., '1 hour', '1 day')")
    
    # Volume measurements
    inflow_volume: float = Field(..., description="Total inflow volume in m³")
    outflow_volume: float = Field(..., description="Total outflow volume in m³")
    balance_volume: float = Field(..., description="Balance (inflow - outflow) in m³")
    
    # Loss analysis
    estimated_seepage: float = Field(default=0.0, description="Estimated seepage loss in m³")
    estimated_evaporation: float = Field(default=0.0, description="Estimated evaporation loss in m³")
    unaccounted_loss: float = Field(default=0.0, description="Unaccounted water loss in m³")
    total_loss: float = Field(default=0.0, description="Total water loss in m³")
    
    # Efficiency metrics
    efficiency_percent: float = Field(..., ge=0.0, le=100.0, description="Water use efficiency percentage")
    loss_percent: float = Field(..., ge=0.0, le=100.0, description="Water loss percentage")
    
    # Contributing locations
    inflow_locations: List[Dict[str, float]] = Field(..., description="Inflow locations with volumes")
    outflow_locations: List[Dict[str, float]] = Field(..., description="Outflow locations with volumes")
    
    class Config:
        from_attributes = True


class FlowAnomaly(BaseModel):
    """Flow anomaly detection result"""
    anomaly_id: Optional[UUID] = None
    location_id: UUID
    location_name: str
    timestamp: datetime
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    
    # Anomaly details
    detected_value: float = Field(..., description="Detected anomalous value")
    expected_value: float = Field(..., description="Expected normal value")
    deviation: float = Field(..., description="Deviation from expected value")
    deviation_percentage: float = Field(..., description="Deviation percentage")
    
    # Context
    sensor_id: Optional[UUID] = None
    description: str
    probable_causes: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    
    # Resolution tracking
    resolved: bool = Field(default=False)
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    
    class Config:
        from_attributes = True
        use_enum_values = True


class EfficiencyMetrics(BaseModel):
    """Network efficiency metrics"""
    segment_id: UUID
    segment_name: str
    time_period: str
    start_time: datetime
    end_time: datetime
    
    # Efficiency indicators
    conveyance_efficiency: float = Field(..., ge=0.0, le=100.0, description="Conveyance efficiency %")
    distribution_efficiency: float = Field(..., ge=0.0, le=100.0, description="Distribution efficiency %")
    application_efficiency: float = Field(..., ge=0.0, le=100.0, description="Application efficiency %")
    overall_efficiency: float = Field(..., ge=0.0, le=100.0, description="Overall system efficiency %")
    
    # Volume metrics
    total_inflow: float = Field(..., description="Total inflow volume in m³")
    total_delivered: float = Field(..., description="Total delivered volume in m³")
    total_losses: float = Field(..., description="Total losses in m³")
    
    # Loss breakdown
    seepage_loss: float = Field(default=0.0, description="Seepage loss in m³")
    evaporation_loss: float = Field(default=0.0, description="Evaporation loss in m³")
    operational_loss: float = Field(default=0.0, description="Operational loss in m³")
    
    # Performance indicators
    performance_score: float = Field(..., ge=0.0, le=100.0, description="Overall performance score")
    recommendations: List[str] = Field(default_factory=list)


class FlowForecast(BaseModel):
    """Flow forecast results"""
    location_id: UUID
    location_name: str
    forecast_time: datetime
    forecast_horizon_hours: int
    
    # Forecast values
    forecasts: List[Dict[str, Any]] = Field(..., description="Time series forecast values")
    
    # Confidence intervals
    confidence_level: float = Field(default=0.95, description="Confidence level for intervals")
    upper_bound: List[float] = Field(..., description="Upper confidence bound")
    lower_bound: List[float] = Field(..., description="Lower confidence bound")
    
    # Model information
    model_type: str = Field(..., description="Forecasting model used")
    model_accuracy: float = Field(..., ge=0.0, le=100.0, description="Model accuracy percentage")
    
    # Risk assessment
    flood_risk: str = Field(..., description="Flood risk level (low, medium, high)")
    drought_risk: str = Field(..., description="Drought risk level (low, medium, high)")
    
    metadata: Optional[Dict[str, Any]] = None