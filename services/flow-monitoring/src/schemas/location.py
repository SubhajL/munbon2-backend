from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID
from enum import Enum


class LocationType(str, Enum):
    """Types of monitoring locations"""
    CANAL = "canal"
    GATE = "gate"
    WEIR = "weir"
    PUMP_STATION = "pump_station"
    RESERVOIR = "reservoir"
    JUNCTION = "junction"
    FIELD_OUTLET = "field_outlet"
    MEASUREMENT_POINT = "measurement_point"


class HydraulicParameters(BaseModel):
    """Hydraulic parameters for a location"""
    channel_width: Optional[float] = Field(None, description="Channel width in meters")
    channel_depth: Optional[float] = Field(None, description="Channel depth in meters")
    channel_slope: Optional[float] = Field(None, description="Channel slope (dimensionless)")
    manning_coefficient: Optional[float] = Field(None, description="Manning's roughness coefficient")
    cross_section_type: Optional[str] = Field(None, description="Cross-section shape (rectangular, trapezoidal, circular)")
    cross_section_params: Optional[Dict[str, float]] = None
    
    # Gate/weir specific parameters
    gate_width: Optional[float] = Field(None, description="Gate width in meters")
    gate_height: Optional[float] = Field(None, description="Gate height in meters")
    discharge_coefficient: Optional[float] = Field(None, description="Discharge coefficient")
    
    # Rating curve parameters
    rating_curve_coefficients: Optional[Dict[str, float]] = None
    rating_curve_type: Optional[str] = Field(None, description="Rating curve type (power, polynomial)")


class MonitoringLocation(BaseModel):
    """Monitoring location details"""
    location_id: UUID
    location_name: str
    location_type: LocationType
    channel_id: str = Field(default="main")
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    elevation: Optional[float] = Field(None, description="Elevation in meters MSL")
    
    # Network topology
    upstream_locations: List[UUID] = Field(default_factory=list)
    downstream_locations: List[UUID] = Field(default_factory=list)
    
    # Hydraulic parameters
    hydraulic_params: Optional[HydraulicParameters] = None
    
    # Operational parameters
    normal_flow_range: Optional[Dict[str, float]] = Field(None, description="Normal flow range (min, max) in m³/s")
    alert_thresholds: Optional[Dict[str, float]] = Field(None, description="Alert thresholds for various parameters")
    
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True
        use_enum_values = True


class LocationNetwork(BaseModel):
    """Network of connected locations"""
    root_location_id: UUID
    locations: List[MonitoringLocation]
    connections: List[Dict[str, Any]] = Field(..., description="Network connections with properties")
    
    def get_upstream_locations(self, location_id: UUID) -> List[UUID]:
        """Get all upstream locations for a given location"""
        location = next((loc for loc in self.locations if loc.location_id == location_id), None)
        return location.upstream_locations if location else []
    
    def get_downstream_locations(self, location_id: UUID) -> List[UUID]:
        """Get all downstream locations for a given location"""
        location = next((loc for loc in self.locations if loc.location_id == location_id), None)
        return location.downstream_locations if location else []