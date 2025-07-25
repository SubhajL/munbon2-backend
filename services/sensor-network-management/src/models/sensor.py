from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum
from sqlalchemy import Column, String, Float, DateTime, Enum as SQLEnum, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SensorType(str, Enum):
    WATER_LEVEL = "water_level"
    MOISTURE = "moisture"

class SensorStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MOVING = "moving"
    MAINTENANCE = "maintenance"
    FAULTY = "faulty"

class SensorDB(Base):
    __tablename__ = "sensors"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(SQLEnum(SensorType), nullable=False)
    status = Column(SQLEnum(SensorStatus), default=SensorStatus.INACTIVE)
    battery_level = Column(Float, default=100.0)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    current_section_id = Column(String, nullable=True)
    last_reading = Column(DateTime, nullable=True)
    last_calibration = Column(DateTime, nullable=True)
    installation_date = Column(DateTime, nullable=True)
    firmware_version = Column(String, nullable=True)
    accuracy_rating = Column(Float, default=1.0)  # 0-1 scale
    movement_count = Column(Integer, default=0)
    total_operational_hours = Column(Float, default=0.0)
    last_maintenance = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Sensor(BaseModel):
    id: str
    name: str
    type: SensorType
    status: SensorStatus = SensorStatus.INACTIVE
    battery_level: float = Field(ge=0, le=100)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    current_section_id: Optional[str] = None
    last_reading: Optional[datetime] = None
    last_calibration: Optional[datetime] = None
    installation_date: Optional[datetime] = None
    firmware_version: Optional[str] = None
    accuracy_rating: float = Field(ge=0, le=1, default=1.0)
    movement_count: int = 0
    total_operational_hours: float = 0.0
    last_maintenance: Optional[datetime] = None

class SensorReading(BaseModel):
    sensor_id: str
    timestamp: datetime
    value: float
    unit: str
    quality: float = Field(ge=0, le=1)  # Data quality indicator
    battery_level: float
    latitude: float
    longitude: float
    section_id: Optional[str] = None

class SensorUpdate(BaseModel):
    status: Optional[SensorStatus] = None
    battery_level: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    current_section_id: Optional[str] = None
    firmware_version: Optional[str] = None

class SensorCalibration(BaseModel):
    sensor_id: str
    calibration_date: datetime
    reference_value: float
    measured_value: float
    adjustment_factor: float
    technician_id: str
    notes: Optional[str] = None