"""Transit loss tracking models"""

from sqlalchemy import Column, String, Float, Integer, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..database import Base

class LossType(enum.Enum):
    """Types of water losses"""
    SEEPAGE = "seepage"
    EVAPORATION = "evaporation"
    OPERATIONAL = "operational"
    STRUCTURAL = "structural"
    UNKNOWN = "unknown"

class TransitLoss(Base):
    """Detailed transit loss records"""
    __tablename__ = "transit_losses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    delivery_id = Column(Integer, ForeignKey("water_deliveries.id"), nullable=False)
    
    # Loss characteristics
    loss_type = Column(Enum(LossType), nullable=False)
    loss_volume_m3 = Column(Float, nullable=False)
    loss_percentage = Column(Float)  # Percentage of flow
    
    # Location information
    canal_segment = Column(String)  # Which segment
    start_chainage_km = Column(Float)  # Start location
    end_chainage_km = Column(Float)  # End location
    
    # Calculation parameters
    flow_rate_m3s = Column(Float)  # Average flow rate
    transit_time_hours = Column(Float)  # Time in segment
    wetted_perimeter_m = Column(Float)  # For seepage calc
    water_temperature_c = Column(Float)  # For evaporation
    
    # Environmental factors
    air_temperature_c = Column(Float)
    humidity_percent = Column(Float)
    wind_speed_ms = Column(Float)
    solar_radiation_wm2 = Column(Float)
    
    # Seepage specific
    soil_type = Column(String)
    canal_condition = Column(String)
    seepage_rate_m3_per_m2_per_day = Column(Float)
    
    # Calculation method
    calculation_method = Column(String)
    calculation_parameters = Column(JSON)
    confidence_level = Column(Float)  # 0-1
    
    # Metadata
    calculated_at = Column(DateTime, server_default=func.now())
    notes = Column(String)
    
    # Relationship
    delivery = relationship("WaterDelivery", back_populates="transit_losses")