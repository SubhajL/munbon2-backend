"""Section model for water accounting"""

from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class Section(Base):
    """Irrigation section (50-200 hectares)"""
    __tablename__ = "sections"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    zone_id = Column(String, nullable=False)
    area_hectares = Column(Float, nullable=False)
    
    # Delivery gate association
    primary_gate_id = Column(String, nullable=False)
    secondary_gate_ids = Column(JSON, default=list)  # List of additional gates
    
    # Physical characteristics
    canal_length_km = Column(Float, nullable=False)  # Length of distribution canals
    canal_type = Column(String, default="earthen")  # earthen, lined, concrete
    seepage_coefficient = Column(Float, nullable=False)  # Custom seepage rate
    
    # Crop information
    primary_crop = Column(String)
    crop_stage = Column(String)  # vegetative, reproductive, maturation
    planting_date = Column(DateTime)
    
    # Status
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    metrics = relationship("SectionMetrics", back_populates="section", cascade="all, delete-orphan")
    deliveries = relationship("WaterDelivery", back_populates="section", cascade="all, delete-orphan")


class SectionMetrics(Base):
    """Current metrics for a section"""
    __tablename__ = "section_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(String, ForeignKey("sections.id"), nullable=False)
    
    # Water balance metrics
    total_delivered_m3 = Column(Float, default=0.0)
    total_losses_m3 = Column(Float, default=0.0)
    total_applied_m3 = Column(Float, default=0.0)
    total_return_flow_m3 = Column(Float, default=0.0)
    
    # Efficiency metrics
    delivery_efficiency = Column(Float)  # Applied/Delivered
    application_efficiency = Column(Float)  # Used/Applied
    overall_efficiency = Column(Float)  # Used/Delivered
    
    # Deficit tracking
    current_deficit_m3 = Column(Float, default=0.0)
    accumulated_deficit_m3 = Column(Float, default=0.0)
    deficit_weeks = Column(Integer, default=0)
    
    # Time period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    last_updated = Column(DateTime, server_default=func.now())
    
    # Relationship
    section = relationship("Section", back_populates="metrics")