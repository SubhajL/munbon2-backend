from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from uuid import UUID


class FlowReadingBase(BaseModel):
    """Base flow reading data"""
    sensor_id: UUID
    location_id: UUID
    channel_id: str = Field(default="main")
    flow_rate: float = Field(..., description="Flow rate in m³/s")
    velocity: float = Field(default=0.0, description="Water velocity in m/s")
    water_level: float = Field(default=0.0, description="Water level in meters")
    pressure: float = Field(default=0.0, description="Pressure in kPa")
    quality_flag: int = Field(default=1, ge=0, le=5, description="Data quality flag (0-5)")
    
    @validator('flow_rate')
    def validate_flow_rate(cls, v):
        if v < 0:
            raise ValueError("Flow rate cannot be negative")
        if v > 10000:
            raise ValueError("Flow rate exceeds maximum expected value")
        return v
    
    @validator('water_level')
    def validate_water_level(cls, v):
        if v < 0:
            raise ValueError("Water level cannot be negative")
        if v > 50:
            raise ValueError("Water level exceeds maximum expected value")
        return v


class FlowReading(FlowReadingBase):
    """Flow reading with timestamp"""
    timestamp: datetime
    sensor_type: str
    
    class Config:
        from_attributes = True


class FlowReadingCreate(FlowReadingBase):
    """Schema for creating flow readings"""
    sensor_type: str
    timestamp: Optional[datetime] = None
    
    @validator('timestamp', pre=True, always=True)
    def set_timestamp(cls, v):
        return v or datetime.utcnow()


class FlowAggregate(BaseModel):
    """Aggregated flow data"""
    time: datetime
    location_id: UUID
    channel_id: str = "main"
    avg_flow_rate: float
    max_flow_rate: float
    min_flow_rate: float
    total_volume: float = Field(..., description="Total volume in m³")
    avg_water_level: float
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    
    class Config:
        from_attributes = True


class FlowHistory(BaseModel):
    """Historical flow data response"""
    location_id: UUID
    channel_id: str
    start_time: datetime
    end_time: datetime
    interval: str
    data: List[FlowAggregate]
    statistics: Dict[str, float]


class VolumeData(BaseModel):
    """Volume calculation data"""
    location_id: UUID
    channel_id: str = "main"
    start_time: datetime
    end_time: datetime
    total_volume: float = Field(..., description="Total volume in m³")
    average_flow_rate: float = Field(..., description="Average flow rate in m³/s")
    peak_flow_rate: float = Field(..., description="Peak flow rate in m³/s")
    min_flow_rate: float = Field(..., description="Minimum flow rate in m³/s")
    
    class Config:
        from_attributes = True


class WaterLevel(BaseModel):
    """Water level data"""
    location_id: UUID
    channel_id: str = "main"
    timestamp: datetime
    water_level: float = Field(..., description="Water level in meters")
    reference_level: float = Field(..., description="Reference level in meters MSL")
    alert_level: Optional[float] = Field(None, description="Alert threshold level")
    critical_level: Optional[float] = Field(None, description="Critical threshold level")
    
    @property
    def absolute_level(self) -> float:
        """Calculate absolute water level"""
        return self.reference_level + self.water_level
    
    @property
    def is_alert(self) -> bool:
        """Check if water level exceeds alert threshold"""
        return self.alert_level is not None and self.water_level >= self.alert_level
    
    @property
    def is_critical(self) -> bool:
        """Check if water level exceeds critical threshold"""
        return self.critical_level is not None and self.water_level >= self.critical_level


class RealtimeFlowResponse(BaseModel):
    """Real-time flow data response"""
    location_id: UUID
    location_name: str
    timestamp: datetime
    flow_data: FlowReading
    water_level: WaterLevel
    status: str = Field(..., description="Operational status")
    anomalies: List[str] = Field(default_factory=list)
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)