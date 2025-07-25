"""Efficiency tracking models"""

from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class EfficiencyRecord(Base):
    """Record of efficiency metrics for a delivery"""
    __tablename__ = "efficiency_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(String, ForeignKey("sections.id"), nullable=False)
    delivery_id = Column(String, nullable=False)
    
    # Volumes
    delivered_volume_m3 = Column(Float, nullable=False)
    applied_volume_m3 = Column(Float, nullable=False)
    consumed_volume_m3 = Column(Float, nullable=False)
    return_flow_m3 = Column(Float, default=0.0)
    
    # Efficiency metrics
    conveyance_efficiency = Column(Float)  # Section inflow / Gate outflow
    application_efficiency = Column(Float)  # Consumed / Applied
    overall_efficiency = Column(Float)  # Consumed / Delivered
    
    # Loss breakdown
    seepage_loss_m3 = Column(Float, default=0.0)
    evaporation_loss_m3 = Column(Float, default=0.0)
    operational_loss_m3 = Column(Float, default=0.0)  # Spills, overflows
    
    # Performance indicators
    uniformity_coefficient = Column(Float)  # Distribution uniformity
    adequacy_indicator = Column(Float)  # Delivered vs Required
    
    # Time period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Metadata
    calculation_method = Column(String)
    data_quality_score = Column(Float)  # 0-1 confidence in data
    created_at = Column(DateTime, server_default=func.now())


class EfficiencyReport(Base):
    """Aggregated efficiency report for sections"""
    __tablename__ = "efficiency_reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String, unique=True, nullable=False)
    
    # Report scope
    report_type = Column(String)  # daily, weekly, seasonal
    zone_id = Column(String)
    section_ids = Column(JSON)  # List of sections included
    
    # Time period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Aggregate metrics
    total_sections = Column(Integer)
    total_deliveries = Column(Integer)
    total_volume_delivered_m3 = Column(Float)
    total_volume_consumed_m3 = Column(Float)
    
    # Average efficiencies
    avg_conveyance_efficiency = Column(Float)
    avg_application_efficiency = Column(Float)
    avg_overall_efficiency = Column(Float)
    
    # Performance distribution
    sections_above_target = Column(Integer)  # Meeting efficiency targets
    sections_below_target = Column(Integer)
    efficiency_distribution = Column(JSON)  # Histogram data
    
    # Key findings
    best_performing_sections = Column(JSON)  # Top 5
    worst_performing_sections = Column(JSON)  # Bottom 5
    improvement_recommendations = Column(JSON)
    
    # Metadata
    generated_by = Column(String)
    generated_at = Column(DateTime, server_default=func.now())
    report_data = Column(JSON)  # Full report data for export