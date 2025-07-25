from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, Field
import strawberry


class Section(BaseModel):
    section_id: str
    zone: int
    area_rai: float
    crop_type: str
    soil_type: str
    elevation_m: float
    delivery_gate: str
    geometry: Optional[Dict] = None  # GeoJSON geometry
    
    class Config:
        json_schema_extra = {
            "example": {
                "section_id": "Zone_2_Section_A",
                "zone": 2,
                "area_rai": 940.625,  # 150.5 hectares * 6.25
                "crop_type": "rice",
                "soil_type": "clay_loam",
                "elevation_m": 218.5,
                "delivery_gate": "M(0,2)->Zone_2"
            }
        }


class SectionDemand(BaseModel):
    section_id: str
    area_rai: float
    crop_type: str
    growth_stage: str
    water_demand_m3: float = Field(ge=0)
    priority: int = Field(ge=1, le=10)
    delivery_window: Dict[str, datetime]
    moisture_deficit_percent: Optional[float] = Field(None, ge=0, le=100)
    stress_level: Optional[str] = Field(None, pattern="^(none|mild|moderate|severe|critical)$")
    
    class Config:
        json_schema_extra = {
            "example": {
                "section_id": "Zone_2_Section_A",
                "area_rai": 940.625,  # 150.5 hectares * 6.25
                "crop_type": "rice",
                "growth_stage": "flowering",
                "water_demand_m3": 15000,
                "priority": 9,
                "delivery_window": {
                    "start": "2024-01-16T06:00:00Z",
                    "end": "2024-01-18T18:00:00Z"
                },
                "moisture_deficit_percent": 35.5,
                "stress_level": "moderate"
            }
        }


class SectionPerformance(BaseModel):
    section_id: str
    week: str
    planned_m3: float
    delivered_m3: float
    efficiency: float = Field(ge=0, le=1)
    deficit_m3: float
    delivery_times: List[datetime]
    average_flow_m3s: Optional[float]
    
    class Config:
        json_schema_extra = {
            "example": {
                "section_id": "Zone_2_Section_A",
                "week": "2024-W03",
                "planned_m3": 15000,
                "delivered_m3": 14250,
                "efficiency": 0.95,
                "deficit_m3": 750,
                "delivery_times": [
                    "2024-01-16T08:00:00Z",
                    "2024-01-17T14:00:00Z"
                ],
                "average_flow_m3s": 2.5
            }
        }


# GraphQL Types
@strawberry.type
class SectionType:
    section_id: str
    zone: int
    area_rai: float
    crop_type: str
    soil_type: str
    elevation_m: float
    delivery_gate: str
    
    @strawberry.field
    async def current_demand(self) -> Optional["SectionDemandType"]:
        # Will be resolved by data loader
        return None
    
    @strawberry.field
    async def performance_history(self, weeks: int = 4) -> List["SectionPerformanceType"]:
        # Will be resolved by data loader
        return []


@strawberry.type
class SectionDemandType:
    section_id: str
    water_demand_m3: float
    priority: int
    growth_stage: str
    moisture_deficit_percent: Optional[float]
    stress_level: Optional[str]


@strawberry.type
class SectionPerformanceType:
    week: str
    planned_m3: float
    delivered_m3: float
    efficiency: float
    deficit_m3: float