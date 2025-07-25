from typing import List, Optional, Dict
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import strawberry


class DemandPriorityEnum(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DemandSubmission(BaseModel):
    week: str = Field(..., pattern="^\\d{4}-W\\d{2}$")
    demands: List[Dict]
    weather_adjustment: Optional[float] = Field(1.0, ge=0.5, le=1.5)
    rainfall_forecast_mm: Optional[float] = Field(0, ge=0)
    
    class Config:
        json_schema_extra = {
            "example": {
                "week": "2024-W03",
                "demands": [
                    {
                        "section_id": "Zone_2_Section_A",
                        "volume_m3": 15000,
                        "priority": "critical"
                    }
                ],
                "weather_adjustment": 0.9,
                "rainfall_forecast_mm": 10
            }
        }


class AggregatedDemand(BaseModel):
    delivery_gate: str
    total_demand_m3: float
    sections: List[str]
    weighted_priority: float
    delivery_window: Dict[str, datetime]
    aggregation_method: str = "weighted_average"
    
    class Config:
        json_schema_extra = {
            "example": {
                "delivery_gate": "M(0,2)->Zone_2",
                "total_demand_m3": 45000,
                "sections": ["Zone_2_Section_A", "Zone_2_Section_B", "Zone_2_Section_C"],
                "weighted_priority": 8.5,
                "delivery_window": {
                    "start": "2024-01-16T06:00:00Z",
                    "end": "2024-01-18T18:00:00Z"
                },
                "aggregation_method": "weighted_average"
            }
        }


class DemandPriority(BaseModel):
    section_id: str
    base_priority: int = Field(ge=1, le=10)
    crop_stage_factor: float = Field(ge=0, le=1)
    moisture_deficit_factor: float = Field(ge=0, le=1)
    economic_value_factor: float = Field(ge=0, le=1)
    stress_indicator_factor: float = Field(ge=0, le=1)
    final_priority: float = Field(ge=0, le=10)
    priority_class: DemandPriorityEnum
    
    class Config:
        json_schema_extra = {
            "example": {
                "section_id": "Zone_2_Section_A",
                "base_priority": 8,
                "crop_stage_factor": 0.9,
                "moisture_deficit_factor": 0.8,
                "economic_value_factor": 0.7,
                "stress_indicator_factor": 0.85,
                "final_priority": 8.2,
                "priority_class": "critical"
            }
        }


# GraphQL Types
@strawberry.type
class DemandSubmissionResult:
    schedule_id: str
    status: str
    conflicts: List[str]
    estimated_completion: datetime
    total_sections: int
    total_volume_m3: float


@strawberry.input
class DemandInput:
    section_id: str
    volume_m3: float
    priority: str


@strawberry.input
class WeeklyDemandInput:
    week: str
    demands: List[DemandInput]
    weather_adjustment: Optional[float] = 1.0
    rainfall_forecast_mm: Optional[float] = 0