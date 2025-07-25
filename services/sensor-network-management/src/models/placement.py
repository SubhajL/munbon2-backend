from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from enum import Enum

class PlacementPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class PlacementReason(str, Enum):
    SCHEDULED_IRRIGATION = "scheduled_irrigation"
    HISTORICAL_PROBLEMS = "historical_problems"
    GATE_AUTOMATION = "gate_automation"
    MANUAL_VALIDATION = "manual_validation"
    WATER_SHORTAGE = "water_shortage"
    MAINTENANCE_CHECK = "maintenance_check"
    CALIBRATION = "calibration"

class SensorPlacement(BaseModel):
    sensor_id: str
    section_id: str
    latitude: float
    longitude: float
    priority: PlacementPriority
    reasons: List[PlacementReason]
    estimated_duration_days: int
    expected_readings_per_day: int
    placement_date: datetime
    removal_date: Optional[datetime] = None

class PlacementRecommendation(BaseModel):
    section_id: str
    priority: PlacementPriority
    score: float = Field(ge=0, le=1)
    reasons: List[PlacementReason]
    recommended_sensor_type: str
    optimal_coordinates: Dict[str, float]  # {"lat": x, "lon": y}
    expected_benefit: float
    historical_accuracy: float
    nearby_sections: List[str]  # Sections that can benefit from this placement
    
class OptimizationRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    include_irrigation_schedule: bool = True
    include_historical_data: bool = True
    include_weather_forecast: bool = True
    max_movements_per_week: int = Field(default=7, le=20)
    minimize_travel_distance: bool = True

class OptimizationResult(BaseModel):
    optimization_id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    placements: List[SensorPlacement]
    total_movements: int
    total_travel_distance_km: float
    coverage_score: float = Field(ge=0, le=1)
    expected_data_quality: float = Field(ge=0, le=1)
    recommendations: List[PlacementRecommendation]
    unmonitored_critical_sections: List[str]
    
class PlacementHistory(BaseModel):
    sensor_id: str
    section_id: str
    start_date: datetime
    end_date: datetime
    readings_collected: int
    average_data_quality: float
    issues_detected: int
    battery_consumed: float
    weather_conditions: Dict[str, any]