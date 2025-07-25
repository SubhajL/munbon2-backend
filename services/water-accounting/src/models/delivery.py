"""Water delivery tracking models"""

from sqlalchemy import Column, String, Float, Integer, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..database import Base

class DeliveryStatus(enum.Enum):
    """Status of water delivery"""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"

class WaterDelivery(Base):
    """Record of water delivery to a section"""
    __tablename__ = "water_deliveries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    delivery_id = Column(String, unique=True, nullable=False)  # External ID
    section_id = Column(String, ForeignKey("sections.id"), nullable=False)
    
    # Schedule information
    scheduled_start = Column(DateTime, nullable=False)
    scheduled_end = Column(DateTime, nullable=False)
    scheduled_volume_m3 = Column(Float, nullable=False)
    
    # Actual delivery
    actual_start = Column(DateTime)
    actual_end = Column(DateTime)
    status = Column(Enum(DeliveryStatus), default=DeliveryStatus.SCHEDULED)
    
    # Volume tracking
    gate_outflow_m3 = Column(Float, default=0.0)  # Volume at gate
    section_inflow_m3 = Column(Float, default=0.0)  # Volume reaching section
    transit_loss_m3 = Column(Float, default=0.0)  # Loss during transit
    
    # Flow integration data
    flow_readings = Column(JSON)  # List of {timestamp, flow_rate} readings
    integration_method = Column(String, default="trapezoidal")
    
    # Delivery path
    delivery_gates = Column(JSON)  # List of gates used
    canal_segments = Column(JSON)  # Canal segments traversed
    travel_time_minutes = Column(Float)
    
    # Conditions
    weather_conditions = Column(JSON)  # Temperature, humidity, wind
    canal_condition = Column(String)  # Good, fair, poor
    
    # Metadata
    operator_id = Column(String)
    notes = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    section = relationship("Section", back_populates="deliveries")
    transit_losses = relationship("TransitLoss", back_populates="delivery", cascade="all, delete-orphan")