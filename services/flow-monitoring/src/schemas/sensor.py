from datetime import datetime, date
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from uuid import UUID
from enum import Enum


class SensorType(str, Enum):
    """Types of flow sensors"""
    ULTRASONIC = "ultrasonic"
    ELECTROMAGNETIC = "electromagnetic"
    MECHANICAL = "mechanical"
    PRESSURE = "pressure"
    RADAR = "radar"
    ACOUSTIC_DOPPLER = "acoustic_doppler"


class SensorStatus(str, Enum):
    """Sensor operational status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    FAULTY = "faulty"
    CALIBRATING = "calibrating"


class CalibrationParams(BaseModel):
    """Sensor calibration parameters"""
    offset: float = Field(default=0.0, description="Zero offset correction")
    scale_factor: float = Field(default=1.0, description="Scale factor correction")
    polynomial_coefficients: Optional[List[float]] = Field(None, description="Polynomial correction coefficients")
    temperature_compensation: Optional[Dict[str, float]] = None
    pressure_compensation: Optional[Dict[str, float]] = None
    custom_params: Optional[Dict[str, Any]] = None


class SensorConfig(BaseModel):
    """Sensor configuration"""
    sensor_id: UUID
    sensor_type: SensorType
    location_id: UUID
    channel_id: str = Field(default="main")
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    installation_date: Optional[date] = None
    calibration_date: Optional[date] = None
    calibration_params: CalibrationParams
    status: SensorStatus = Field(default=SensorStatus.ACTIVE)
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True
        use_enum_values = True


class SensorCalibration(BaseModel):
    """Sensor calibration request"""
    sensor_id: UUID
    calibration_type: str = Field(..., description="Type of calibration (manual, automatic, factory)")
    new_params: CalibrationParams
    performed_by: str
    notes: Optional[str] = None
    reference_values: Optional[Dict[str, float]] = Field(None, description="Reference measurements used for calibration")


class CalibrationHistory(BaseModel):
    """Calibration history record"""
    calibration_id: UUID
    sensor_id: UUID
    calibration_date: datetime
    calibration_type: str
    old_params: Optional[CalibrationParams] = None
    new_params: CalibrationParams
    performed_by: str
    notes: Optional[str] = None
    
    class Config:
        from_attributes = True


class SensorHealthMetrics(BaseModel):
    """Sensor health and performance metrics"""
    sensor_id: UUID
    last_reading: Optional[datetime] = None
    total_readings: int = Field(default=0)
    error_count: int = Field(default=0)
    uptime_percentage: float = Field(default=100.0, ge=0.0, le=100.0)
    average_quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    drift_detected: bool = Field(default=False)
    maintenance_required: bool = Field(default=False)
    last_maintenance: Optional[date] = None
    next_calibration_due: Optional[date] = None