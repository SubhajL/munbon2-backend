from typing import List, Optional, Dict
from datetime import datetime
from pydantic import BaseModel, Field
import strawberry


class DeliveryPoint(BaseModel):
    gate_id: str
    location: Dict[str, float]  # {"lat": ..., "lon": ...}
    sections_served: List[str]
    max_flow_m3s: float
    current_flow_m3s: Optional[float] = 0
    elevation_m: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "gate_id": "M(0,2)->Zone_2",
                "location": {"lat": 14.8234, "lon": 103.1567},
                "sections_served": ["Zone_2_Section_A", "Zone_2_Section_B"],
                "max_flow_m3s": 5.0,
                "current_flow_m3s": 2.8,
                "elevation_m": 218.5
            }
        }


class DeliveryPerformance(BaseModel):
    section_id: str
    delivery_gate: str
    week: str
    planned_volume_m3: float
    delivered_volume_m3: float
    delivery_efficiency: float = Field(ge=0, le=1)
    losses_m3: float
    deficit_m3: float
    delivery_dates: List[datetime]
    
    class Config:
        json_schema_extra = {
            "example": {
                "section_id": "Zone_2_Section_A",
                "delivery_gate": "M(0,2)->Zone_2",
                "week": "2024-W03",
                "planned_volume_m3": 15000,
                "delivered_volume_m3": 14250,
                "delivery_efficiency": 0.95,
                "losses_m3": 750,
                "deficit_m3": 750,
                "delivery_dates": [
                    "2024-01-16T08:00:00Z",
                    "2024-01-17T14:00:00Z"
                ]
            }
        }


class DeliveryFeedback(BaseModel):
    week: str
    sections: List[Dict[str, float]]  # section_id -> delivered_m3
    gate_performances: Dict[str, float]  # gate_id -> efficiency
    total_delivered_m3: float
    total_losses_m3: float
    overall_efficiency: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "week": "2024-W03",
                "sections": [
                    {"Zone_2_Section_A": 14250},
                    {"Zone_2_Section_B": 11400}
                ],
                "gate_performances": {
                    "M(0,2)->Zone_2": 0.92,
                    "M(0,5)->Zone_5": 0.88
                },
                "total_delivered_m3": 75000,
                "total_losses_m3": 5000,
                "overall_efficiency": 0.90
            }
        }


# GraphQL Types
@strawberry.type
class DeliveryPointType:
    gate_id: str
    location_lat: float
    location_lon: float
    sections_served: List[str]
    max_flow_m3s: float
    current_flow_m3s: float
    
    @strawberry.field
    async def recent_performance(self) -> Optional["DeliveryPerformanceType"]:
        # Will be resolved by data loader
        return None


@strawberry.type
class DeliveryPerformanceType:
    planned: float
    actual: float
    efficiency: float
    deficit: float


@strawberry.type
class PerformanceSummary:
    week: str
    total_planned_m3: float
    total_delivered_m3: float
    overall_efficiency: float
    sections_served: int
    sections_with_deficit: int