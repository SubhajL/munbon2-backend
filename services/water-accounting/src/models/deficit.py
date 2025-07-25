"""Deficit tracking models"""

from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class DeficitRecord(Base):
    """Record of water deficits by section"""
    __tablename__ = "deficit_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(String, ForeignKey("sections.id"), nullable=False)
    
    # Time period
    week_number = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Demand and supply
    water_demand_m3 = Column(Float, nullable=False)  # Required water
    water_delivered_m3 = Column(Float, nullable=False)  # Actually delivered
    water_consumed_m3 = Column(Float, nullable=False)  # Actually used
    
    # Deficit calculation
    delivery_deficit_m3 = Column(Float)  # Demand - Delivered
    consumption_deficit_m3 = Column(Float)  # Demand - Consumed
    deficit_percentage = Column(Float)  # Deficit / Demand * 100
    
    # Carry-forward tracking
    previous_deficit_m3 = Column(Float, default=0.0)
    accumulated_deficit_m3 = Column(Float)
    deficit_age_weeks = Column(Integer, default=1)
    
    # Impact assessment
    estimated_yield_impact = Column(Float)  # Percentage yield reduction
    stress_level = Column(String)  # none, mild, moderate, severe
    recovery_priority = Column(Integer)  # 1-10 priority for next cycle
    
    # Compensation
    compensation_scheduled = Column(Boolean, default=False)
    compensation_volume_m3 = Column(Float)
    compensation_date = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class DeficitCarryForward(Base):
    """Track deficit carry-forward between periods"""
    __tablename__ = "deficit_carryforward"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(String, ForeignKey("sections.id"), nullable=False)
    
    # Current status
    active = Column(Boolean, default=True)
    total_deficit_m3 = Column(Float, nullable=False)
    oldest_deficit_week = Column(Integer)
    newest_deficit_week = Column(Integer)
    
    # Deficit aging
    deficit_breakdown = Column(JSON)  # {week: volume} breakdown
    weeks_in_deficit = Column(Integer, default=0)
    
    # Recovery plan
    recovery_plan = Column(JSON)  # Planned compensation schedule
    recovery_status = Column(String)  # pending, in_progress, completed
    recovery_start_date = Column(DateTime)
    recovery_target_date = Column(DateTime)
    
    # Priority and impact
    priority_score = Column(Float)  # Calculated priority
    cumulative_stress_index = Column(Float)  # Accumulated stress
    
    # Historical tracking
    compensation_history = Column(JSON)  # Past compensations
    last_full_delivery = Column(DateTime)  # Last time demand was met
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())