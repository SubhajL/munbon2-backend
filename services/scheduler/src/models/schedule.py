from sqlalchemy import Column, String, Integer, Date, Time, Float, Boolean, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import date, time
from typing import Optional, List, Dict

from ..core.database import Base
from .base import BaseModel


class WeeklySchedule(Base, BaseModel):
    """Master schedule for a week"""
    __tablename__ = "weekly_schedules"
    
    # Schedule identification
    schedule_code = Column(String(50), unique=True, nullable=False)
    week_number = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    
    # Schedule metadata
    status = Column(String(20), default="draft")  # draft, approved, active, completed, cancelled
    version = Column(Integer, default=1)
    
    # Optimization results
    total_water_demand_m3 = Column(Float, nullable=False)
    total_water_allocated_m3 = Column(Float, nullable=False)
    efficiency_percent = Column(Float)
    
    # Field team planning
    total_operations = Column(Integer, nullable=False)
    field_days = Column(ARRAY(Date), nullable=False)  # Days when field teams will operate
    total_travel_km = Column(Float)
    estimated_labor_hours = Column(Float)
    
    # Optimization metadata
    optimization_time_seconds = Column(Float)
    optimization_iterations = Column(Integer)
    objective_value = Column(Float)
    
    # Additional data
    constraints_summary = Column(JSON)  # Summary of applied constraints
    weather_forecast = Column(JSON)  # Weather data used for planning
    notes = Column(Text)
    
    # Relationships
    operations = relationship("ScheduledOperation", back_populates="schedule", cascade="all, delete-orphan")
    instructions = relationship("FieldInstruction", back_populates="schedule", cascade="all, delete-orphan")
    adaptations = relationship("ScheduleAdaptation", back_populates="schedule")


class ScheduledOperation(Base, BaseModel):
    """Individual gate operation in the schedule"""
    __tablename__ = "scheduled_operations"
    
    # Foreign keys
    schedule_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Operation details
    gate_id = Column(String(50), nullable=False)  # e.g., "M(0,0)"
    gate_name = Column(String(100))
    canal_name = Column(String(100))
    zone_id = Column(String(20))
    
    # Timing
    operation_date = Column(Date, nullable=False)
    planned_start_time = Column(Time, nullable=False)
    planned_end_time = Column(Time, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    
    # Gate settings
    current_opening_percent = Column(Float)  # Current gate position
    target_opening_percent = Column(Float, nullable=False)  # Target gate position
    operation_type = Column(String(20))  # open, close, adjust
    
    # Flow information
    expected_flow_before = Column(Float)  # m³/s
    expected_flow_after = Column(Float)  # m³/s
    downstream_impact = Column(JSON)  # List of affected downstream areas
    
    # Assignment
    team_id = Column(String(50))
    team_name = Column(String(100))
    operation_sequence = Column(Integer)  # Order within the team's route
    
    # Location
    latitude = Column(Float)
    longitude = Column(Float)
    location_description = Column(Text)
    
    # Status tracking
    status = Column(String(20), default="scheduled")  # scheduled, in_progress, completed, skipped
    actual_start_time = Column(Time)
    actual_end_time = Column(Time)
    actual_opening_percent = Column(Float)
    
    # Verification
    photo_before_url = Column(String)
    photo_after_url = Column(String)
    operator_notes = Column(Text)
    
    # Relationships
    schedule = relationship("WeeklySchedule", back_populates="operations")


class FieldInstruction(Base, BaseModel):
    """Instructions for field teams"""
    __tablename__ = "field_instructions"
    
    # Foreign keys
    schedule_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Team assignment
    team_id = Column(String(50), nullable=False)
    team_name = Column(String(100))
    operation_date = Column(Date, nullable=False)
    
    # Route information
    start_location = Column(String(200))
    end_location = Column(String(200))
    total_distance_km = Column(Float)
    estimated_duration_hours = Column(Float)
    
    # Operations summary
    total_operations = Column(Integer)
    operation_ids = Column(ARRAY(UUID(as_uuid=True)))  # List of scheduled_operation IDs
    
    # GPS route
    route_coordinates = Column(JSON)  # GeoJSON LineString
    waypoints = Column(JSON)  # List of waypoints with gate info
    
    # Instructions
    general_instructions = Column(Text)
    safety_notes = Column(Text)
    special_equipment = Column(ARRAY(String))
    
    # Contact information
    supervisor_name = Column(String(100))
    supervisor_phone = Column(String(20))
    emergency_contact = Column(String(100))
    
    # Status
    status = Column(String(20), default="pending")  # pending, in_progress, completed
    start_time = Column(Time)
    end_time = Column(Time)
    completion_percent = Column(Float, default=0.0)
    
    # Relationships
    schedule = relationship("WeeklySchedule", back_populates="instructions")


class ScheduleAdaptation(Base, BaseModel):
    """Real-time adaptations to the schedule"""
    __tablename__ = "schedule_adaptations"
    
    # Foreign keys
    schedule_id = Column(UUID(as_uuid=True), nullable=False)
    original_operation_id = Column(UUID(as_uuid=True))  # If adapting specific operation
    
    # Adaptation details
    adaptation_type = Column(String(50))  # gate_failure, weather_change, demand_change, manual_override
    trigger_source = Column(String(50))  # automated, operator, field_team
    
    # Timing
    detected_at = Column(DateTime(timezone=True), nullable=False)
    applied_at = Column(DateTime(timezone=True))
    
    # Changes
    original_state = Column(JSON)  # Original operation details
    adapted_state = Column(JSON)  # New operation details
    affected_operations = Column(ARRAY(UUID(as_uuid=True)))  # Other operations affected
    
    # Reasoning
    reason = Column(Text, nullable=False)
    impact_assessment = Column(JSON)  # Impact on water delivery, efficiency, etc.
    
    # Approval
    requires_approval = Column(Boolean, default=False)
    approval_status = Column(String(20))  # pending, approved, rejected
    approved_by = Column(String(100))
    approval_notes = Column(Text)
    
    # Notification
    teams_notified = Column(ARRAY(String))  # List of team IDs notified
    notification_sent_at = Column(DateTime(timezone=True))
    
    # Relationships
    schedule = relationship("WeeklySchedule", back_populates="adaptations")


class OptimizationConstraint(Base, BaseModel):
    """System constraints for optimization"""
    __tablename__ = "optimization_constraints"
    
    # Constraint identification
    constraint_name = Column(String(100), unique=True, nullable=False)
    constraint_type = Column(String(50))  # capacity, flow, time, resource
    
    # Applicability
    applies_to = Column(String(50))  # canal, gate, zone, team
    entity_id = Column(String(100))  # Specific entity ID if applicable
    
    # Constraint details
    min_value = Column(Float)
    max_value = Column(Float)
    unit = Column(String(20))  # m3/s, percent, hours, etc.
    
    # Time windows
    valid_from = Column(Time)
    valid_to = Column(Time)
    days_of_week = Column(ARRAY(Integer))  # 0=Monday, 6=Sunday
    
    # Priority and flexibility
    priority = Column(Integer, default=1)  # Higher = more important
    is_hard_constraint = Column(Boolean, default=True)
    violation_penalty = Column(Float)  # Cost of violating soft constraint
    
    # Metadata
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    
    
class FieldTeam(Base, BaseModel):
    """Field team information"""
    __tablename__ = "field_teams"
    
    # Team identification
    team_code = Column(String(50), unique=True, nullable=False)
    team_name = Column(String(100), nullable=False)
    
    # Capacity
    max_operations_per_day = Column(Integer, default=30)
    max_travel_km_per_day = Column(Float, default=100)
    work_start_time = Column(Time, default=time(7, 0))
    work_end_time = Column(Time, default=time(17, 0))
    
    # Availability
    available_days = Column(ARRAY(Integer), default=[1, 2, 3, 4, 5])  # Monday to Friday
    base_location_lat = Column(Float)
    base_location_lng = Column(Float)
    
    # Skills and equipment
    can_operate_gates = Column(ARRAY(String))  # Specific gate types they can operate
    has_vehicle = Column(Boolean, default=True)
    special_equipment = Column(ARRAY(String))
    
    # Contact
    supervisor_name = Column(String(100))
    supervisor_phone = Column(String(20))
    team_phone = Column(String(20))
    
    # Status
    is_active = Column(Boolean, default=True)
    current_location_lat = Column(Float)
    current_location_lng = Column(Float)
    last_location_update = Column(DateTime(timezone=True))