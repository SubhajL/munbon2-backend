"""
Database models for field teams.
"""

from sqlalchemy import (
    Column, String, Float, Integer, Boolean, JSON, 
    Date, Time, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from .base import Base


class FieldTeam(Base):
    """Field team model"""
    __tablename__ = "field_teams"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    
    # Base location
    base_location = Column(String(200), nullable=False)
    base_latitude = Column(Float, nullable=False)
    base_longitude = Column(Float, nullable=False)
    
    # Contact information
    primary_phone = Column(String(50), nullable=False)
    secondary_phone = Column(String(50), nullable=True)
    radio_channel = Column(String(50), nullable=True)
    
    # Capabilities
    capabilities = Column(JSON, default=list)
    vehicle_type = Column(String(50), nullable=False)
    vehicle_id = Column(String(100), nullable=True)
    average_speed_kmh = Column(Float, default=40.0)
    
    # Operational parameters
    max_operations_per_day = Column(Integer, default=8)
    operating_hours_start = Column(Time, nullable=False)
    operating_hours_end = Column(Time, nullable=False)
    
    # Service areas
    assigned_zones = Column(JSON, default=list)
    max_travel_radius_km = Column(Float, default=50.0)
    
    # Status
    status = Column(String(50), default="available")
    active = Column(Boolean, default=True)
    
    # Performance metrics
    operations_completed = Column(Integer, default=0)
    average_completion_time = Column(Float, nullable=True)
    on_time_rate = Column(Float, nullable=True)
    
    # Relationships
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    availabilities = relationship("TeamAvailability", back_populates="team", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_team_status_active', 'status', 'active'),
        Index('idx_team_zones', 'assigned_zones'),
    )


class TeamMember(Base):
    """Team member model"""
    __tablename__ = "team_members"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("field_teams.id"), nullable=False)
    
    # Personal information
    member_code = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    role = Column(String(100), nullable=False)
    phone = Column(String(50), nullable=True)
    
    # Skills and experience
    capabilities = Column(JSON, default=list)
    years_experience = Column(Integer, default=0)
    certifications = Column(JSON, default=list)
    
    # Emergency contact
    emergency_contact_name = Column(String(200), nullable=True)
    emergency_contact_phone = Column(String(50), nullable=True)
    
    # Status
    active = Column(Boolean, default=True)
    
    # Relationships
    team = relationship("FieldTeam", back_populates="members")
    
    __table_args__ = (
        Index('idx_member_team', 'team_id'),
        Index('idx_member_active', 'active'),
    )


class TeamAvailability(Base):
    """Team availability schedule"""
    __tablename__ = "team_availabilities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("field_teams.id"), nullable=False)
    
    # Availability period
    date = Column(Date, nullable=False)
    available = Column(Boolean, default=True)
    
    # If not fully available
    reason = Column(String(500), nullable=True)
    available_hours = Column(JSON, nullable=True)  # List of time ranges
    max_operations_override = Column(Integer, nullable=True)
    
    # Relationships
    team = relationship("FieldTeam", back_populates="availabilities")
    
    __table_args__ = (
        UniqueConstraint('team_id', 'date', name='uq_team_date_availability'),
        Index('idx_availability_date', 'date'),
        Index('idx_availability_team_date', 'team_id', 'date'),
    )