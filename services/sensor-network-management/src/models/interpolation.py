from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from enum import Enum

class InterpolationMethod(str, Enum):
    INVERSE_DISTANCE = "inverse_distance"
    KRIGING = "kriging"
    HYDRAULIC_MODEL = "hydraulic_model"
    MACHINE_LEARNING = "machine_learning"
    HYBRID = "hybrid"

class DataQuality(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ESTIMATED = "estimated"

class ConfidenceScore(BaseModel):
    overall: float = Field(ge=0, le=1)
    spatial_coverage: float = Field(ge=0, le=1)
    temporal_coverage: float = Field(ge=0, le=1)
    model_accuracy: float = Field(ge=0, le=1)
    data_freshness: float = Field(ge=0, le=1)
    factors: Dict[str, float]

class InterpolatedData(BaseModel):
    section_id: str
    timestamp: datetime
    parameter: str  # "water_level", "moisture", etc.
    value: float
    unit: str
    confidence: ConfidenceScore
    quality: DataQuality
    method: InterpolationMethod
    source_sensors: List[str]  # IDs of sensors used for interpolation
    distance_to_nearest_sensor_km: float
    hydraulic_factors: Optional[Dict[str, float]] = None
    
class InterpolationRequest(BaseModel):
    section_ids: List[str]
    parameters: List[str]
    timestamp: Optional[datetime] = None
    time_range_hours: Optional[int] = None
    method: Optional[InterpolationMethod] = None
    include_confidence: bool = True
    include_source_data: bool = False
    
class SpatialInterpolationGrid(BaseModel):
    bounds: Dict[str, float]  # {"north": x, "south": y, "east": z, "west": w}
    resolution_m: float
    timestamp: datetime
    parameter: str
    grid_data: List[List[float]]
    confidence_grid: List[List[float]]
    sensor_locations: List[Dict[str, float]]
    
class CalibrationData(BaseModel):
    section_id: str
    timestamp: datetime
    interpolated_value: float
    actual_value: float
    error: float
    error_percentage: float
    method_used: InterpolationMethod
    contributing_sensors: List[str]
    
class InterpolationModelMetrics(BaseModel):
    method: InterpolationMethod
    mae: float  # Mean Absolute Error
    rmse: float  # Root Mean Square Error
    r2_score: float
    samples_count: int
    last_updated: datetime
    spatial_coverage: float
    recommended_max_distance_km: float