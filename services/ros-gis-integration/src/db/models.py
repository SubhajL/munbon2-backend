"""
Database models for ROS/GIS Integration Service
Using SQLAlchemy with asyncpg
"""

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, 
    ForeignKey, UniqueConstraint, CheckConstraint, Numeric, DECIMAL
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from datetime import datetime

Base = declarative_base()


class Section(Base):
    __tablename__ = 'sections'
    __table_args__ = {'schema': 'ros_gis'}
    
    section_id = Column(String(50), primary_key=True)
    zone = Column(Integer, nullable=False)
    area_hectares = Column(DECIMAL(10, 2))
    area_rai = Column(DECIMAL(10, 2))  # Generated column
    crop_type = Column(String(50))
    soil_type = Column(String(50))
    elevation_m = Column(DECIMAL(6, 2))
    delivery_gate = Column(String(50))
    geometry = Column(Geometry('POLYGON', srid=4326))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    demands = relationship("Demand", back_populates="section")
    performances = relationship("SectionPerformance", back_populates="section")
    gate_mappings = relationship("GateMapping", back_populates="section")
    weather_adjustments = relationship("WeatherAdjustment", back_populates="section")


class Demand(Base):
    __tablename__ = 'demands'
    __table_args__ = {'schema': 'ros_gis'}
    
    demand_id = Column(Integer, primary_key=True)
    section_id = Column(String(50), ForeignKey('ros_gis.sections.section_id'))
    week = Column(String(8), nullable=False)
    volume_m3 = Column(DECIMAL(12, 2))
    priority = Column(DECIMAL(3, 1))
    priority_class = Column(String(20))
    crop_type = Column(String(50))
    growth_stage = Column(String(50))
    moisture_deficit_percent = Column(DECIMAL(5, 2))
    stress_level = Column(String(20))
    delivery_window_start = Column(DateTime)
    delivery_window_end = Column(DateTime)
    weather_adjustment_factor = Column(DECIMAL(4, 3), server_default='1.0')
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    section = relationship("Section", back_populates="demands")
    
    __table_args__ = (
        CheckConstraint('priority >= 0 AND priority <= 10'),
        CheckConstraint("priority_class IN ('critical', 'high', 'medium', 'low')"),
        CheckConstraint("stress_level IN ('none', 'mild', 'moderate', 'severe', 'critical')"),
        {'schema': 'ros_gis'}
    )


class SectionPerformance(Base):
    __tablename__ = 'section_performance'
    __table_args__ = {'schema': 'ros_gis'}
    
    performance_id = Column(Integer, primary_key=True)
    section_id = Column(String(50), ForeignKey('ros_gis.sections.section_id'))
    week = Column(String(8), nullable=False)
    planned_m3 = Column(DECIMAL(12, 2))
    delivered_m3 = Column(DECIMAL(12, 2))
    efficiency = Column(DECIMAL(3, 2))
    deficit_m3 = Column(DECIMAL(12, 2))
    delivery_count = Column(Integer, default=0)
    average_flow_m3s = Column(DECIMAL(8, 3))
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    section = relationship("Section", back_populates="performances")
    
    __table_args__ = (
        CheckConstraint('efficiency >= 0 AND efficiency <= 1'),
        {'schema': 'ros_gis'}
    )


class GateMapping(Base):
    __tablename__ = 'gate_mappings'
    __table_args__ = {'schema': 'ros_gis'}
    
    mapping_id = Column(Integer, primary_key=True)
    gate_id = Column(String(50), nullable=False)
    section_id = Column(String(50), ForeignKey('ros_gis.sections.section_id'))
    distance_km = Column(DECIMAL(6, 2))
    travel_time_hours = Column(DECIMAL(5, 2))
    is_primary = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    section = relationship("Section", back_populates="gate_mappings")
    
    __table_args__ = (
        UniqueConstraint('gate_id', 'section_id'),
        {'schema': 'ros_gis'}
    )


class GateDemand(Base):
    __tablename__ = 'gate_demands'
    __table_args__ = {'schema': 'ros_gis'}
    
    gate_demand_id = Column(Integer, primary_key=True)
    gate_id = Column(String(50), nullable=False)
    week = Column(String(8), nullable=False)
    total_volume_m3 = Column(DECIMAL(12, 2))
    section_count = Column(Integer)
    priority_weighted = Column(DECIMAL(3, 1))
    schedule_id = Column(String(100))
    status = Column(String(20), default='pending')
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint('gate_id', 'week'),
        {'schema': 'ros_gis'}
    )


class WeatherAdjustment(Base):
    __tablename__ = 'weather_adjustments'
    __table_args__ = {'schema': 'ros_gis'}
    
    adjustment_id = Column(Integer, primary_key=True)
    section_id = Column(String(50), ForeignKey('ros_gis.sections.section_id'))
    week = Column(String(8), nullable=False)
    rainfall_mm = Column(DECIMAL(6, 2))
    et_mm = Column(DECIMAL(6, 2))
    adjustment_factor = Column(DECIMAL(4, 3))
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    section = relationship("Section", back_populates="weather_adjustments")