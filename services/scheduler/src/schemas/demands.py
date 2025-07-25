"""
Demand-related Pydantic schemas
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


class DemandStatus(str, Enum):
    """Demand processing status"""
    SUBMITTED = "submitted"
    VALIDATED = "validated"
    PROCESSING = "processing"
    SCHEDULED = "scheduled"
    REJECTED = "rejected"
    COMPLETED = "completed"


class CropType(str, Enum):
    """Supported crop types"""
    RICE = "rice"
    CORN = "corn"
    SUGARCANE = "sugarcane"
    VEGETABLES = "vegetables"
    OTHER = "other"


class SectionDemand(BaseModel):
    """Water demand for a section"""
    section_id: str
    zone: int = Field(ge=1, le=10)
    demand_m3: float = Field(gt=0, description="Water demand in cubic meters")
    priority: int = Field(ge=1, le=10, default=5)
    crop_type: str
    delivery_window: Dict[str, datetime] = Field(
        description="Preferred delivery time window"
    )
    current_moisture: Optional[float] = Field(
        None, ge=0, le=100, 
        description="Current soil moisture percentage"
    )
    critical_date: Optional[datetime] = Field(
        None,
        description="Critical date by which water must be delivered"
    )
    
    @validator('crop_type')
    def validate_crop_type(cls, v):
        if v not in [ct.value for ct in CropType]:
            return CropType.OTHER.value
        return v


class DemandSubmission(BaseModel):
    """Demand submission from ROS/GIS service"""
    week: str = Field(description="Week in YYYY-WW format")
    sections: List[SectionDemand]
    total_sections: int
    total_demand_m3: float
    source: str = Field(default="ros_gis_integration")
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    weather_adjustment: Optional[float] = Field(
        None, ge=0.5, le=1.5,
        description="Weather-based adjustment factor"
    )
    
    @validator('week')
    def validate_week_format(cls, v):
        try:
            year, week = v.split('-')
            year = int(year)
            week = int(week)
            if week < 1 or week > 53:
                raise ValueError
        except:
            raise ValueError("Week must be in YYYY-WW format")
        return v
    
    @validator('total_sections')
    def validate_section_count(cls, v, values):
        if 'sections' in values and v != len(values['sections']):
            raise ValueError("Total sections must match section list length")
        return v


class DemandConflict(BaseModel):
    """Conflict between demands"""
    conflict_type: str = Field(description="capacity, timing, or resource")
    severity: str = Field(description="low, medium, high")
    affected_sections: List[str]
    description: str
    potential_impact_m3: float


class DemandValidationResult(BaseModel):
    """Result of demand validation"""
    is_valid: bool
    conflicts: List[DemandConflict]
    warnings: List[str]
    message: str
    total_capacity_available: Optional[float] = None
    total_demand_requested: Optional[float] = None


class DemandResponse(BaseModel):
    """Response to demand submission"""
    schedule_id: Optional[str]
    status: DemandStatus
    conflicts: List[DemandConflict]
    estimated_completion: Optional[str] = None
    message: str


class AggregatedDemands(BaseModel):
    """Aggregated demands for a week"""
    week: str
    total_demand_m3: float
    sections_count: int
    zones_covered: List[int]
    demands_by_zone: Dict[int, float]
    demands_by_crop: Dict[str, float]
    priority_distribution: Dict[int, int]
    created_at: datetime
    last_updated: datetime
    processing_status: DemandStatus


class DemandProcessingStatus(BaseModel):
    """Status of demand processing"""
    schedule_id: str
    status: DemandStatus
    progress_percentage: float
    current_step: str
    estimated_completion: Optional[datetime]
    conflicts_found: int
    warnings: List[str]
    last_updated: datetime