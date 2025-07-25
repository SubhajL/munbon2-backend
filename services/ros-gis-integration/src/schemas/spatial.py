from typing import List, Dict, Optional
from pydantic import BaseModel, Field
import strawberry


class SpatialMapping(BaseModel):
    section_id: str
    delivery_gate: str
    distance_km: float
    elevation_difference_m: float
    delivery_path: List[str]  # Sequence of nodes from gate to section
    travel_time_hours: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "section_id": "Zone_2_Section_A",
                "delivery_gate": "M(0,2)->Zone_2",
                "distance_km": 2.5,
                "elevation_difference_m": -3.2,
                "delivery_path": ["M(0,2)", "Zone_2_Node", "Zone_2_Section_A"],
                "travel_time_hours": 0.75
            }
        }


class GateMapping(BaseModel):
    gate_id: str
    gate_type: str  # "automated" | "manual"
    sections_served: List[str]
    total_area_rai: float
    max_capacity_m3s: float
    current_allocation_m3s: float = 0
    utilization_percent: float = Field(ge=0, le=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "gate_id": "M(0,2)->Zone_2",
                "gate_type": "automated",
                "sections_served": ["Zone_2_Section_A", "Zone_2_Section_B", "Zone_2_Section_C"],
                "total_area_rai": 2815.625,  # 450.5 hectares * 6.25
                "max_capacity_m3s": 5.0,
                "current_allocation_m3s": 3.5,
                "utilization_percent": 70
            }
        }


class SectionBoundary(BaseModel):
    section_id: str
    geometry: Dict  # GeoJSON Polygon
    area_rai: float
    centroid: Dict[str, float]  # {"lat": ..., "lon": ...}
    neighbors: List[str]  # Adjacent section IDs
    
    class Config:
        json_schema_extra = {
            "example": {
                "section_id": "Zone_2_Section_A",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[103.15, 14.82], [103.16, 14.82], [103.16, 14.83], [103.15, 14.83], [103.15, 14.82]]]
                },
                "area_rai": 940.625,  # 150.5 hectares * 6.25
                "centroid": {"lat": 14.825, "lon": 103.155},
                "neighbors": ["Zone_2_Section_B", "Zone_2_Section_D"]
            }
        }


# GraphQL Types
@strawberry.type
class SpatialMappingType:
    section_id: str
    delivery_gate: str
    distance_km: float
    travel_time_hours: float
    
    @strawberry.field
    def is_efficient(self) -> bool:
        # Consider delivery efficient if travel time < 2 hours
        return self.travel_time_hours < 2.0


@strawberry.type
class GateMappingType:
    gate_id: str
    gate_type: str
    sections_count: int
    total_area_rai: float
    utilization_percent: float
    
    @strawberry.field
    def is_overloaded(self) -> bool:
        return self.utilization_percent > 90
    
    @strawberry.field
    def has_capacity(self) -> bool:
        return self.utilization_percent < 80