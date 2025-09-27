"""
SQLAlchemy models for Water Simulation Service
"""

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, ForeignKey, Text, DECIMAL
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()


class Scenario(Base):
    """Simulation scenario configuration"""
    __tablename__ = "scenarios"
    __table_args__ = {"schema": "simulation"}
    
    scenario_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    base_date = Column(DateTime, nullable=False)
    duration_days = Column(Integer, nullable=False)
    time_step_minutes = Column(Integer, nullable=False, default=60)
    optimization_objective = Column(String(50), nullable=False, default="multi_objective")
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSON, default=dict)
    
    # Relationships
    runs = relationship("SimulationRun", back_populates="scenario", cascade="all, delete-orphan")
    section_demands = relationship("SectionDemand", back_populates="scenario", cascade="all, delete-orphan")


class SimulationRun(Base):
    """Individual simulation run instance"""
    __tablename__ = "runs"
    __table_args__ = {"schema": "simulation"}
    
    run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_id = Column(UUID(as_uuid=True), ForeignKey("simulation.scenarios.scenario_id", ondelete="CASCADE"))
    status = Column(String(20), nullable=False, default="pending")
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    current_simulation_time = Column(DateTime)
    progress_percent = Column(DECIMAL(5, 2), default=0)
    error_message = Column(Text)
    statistics = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    scenario = relationship("Scenario", back_populates="runs")
    states = relationship("SimulationState", back_populates="run", cascade="all, delete-orphan")
    gate_operations = relationship("GateOperation", back_populates="run", cascade="all, delete-orphan")
    optimization_results = relationship("OptimizationResult", back_populates="run", cascade="all, delete-orphan")
    analysis_results = relationship("AnalysisResult", back_populates="run", cascade="all, delete-orphan")


class SimulationState(Base):
    """State snapshot at each simulation time step"""
    __tablename__ = "states"
    __table_args__ = {"schema": "simulation"}
    
    state_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("simulation.runs.run_id", ondelete="CASCADE"))
    simulation_time = Column(DateTime, nullable=False)
    time_step = Column(Integer, nullable=False)
    
    # State data
    water_levels = Column(JSON, nullable=False, default=dict)
    gate_positions = Column(JSON, nullable=False, default=dict)
    flow_rates = Column(JSON, nullable=False, default=dict)
    
    # Metrics
    total_demand_m3 = Column(DECIMAL(15, 2))
    total_supply_m3 = Column(DECIMAL(15, 2))
    total_delivered_m3 = Column(DECIMAL(15, 2))
    system_efficiency = Column(DECIMAL(5, 4))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    run = relationship("SimulationRun", back_populates="states")


class SectionDemand(Base):
    """Section-specific demand configuration for scenarios"""
    __tablename__ = "section_demands"
    __table_args__ = {"schema": "simulation"}
    
    demand_id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(UUID(as_uuid=True), ForeignKey("simulation.scenarios.scenario_id", ondelete="CASCADE"))
    section_id = Column(String(50), nullable=False)
    week_number = Column(Integer, nullable=False)
    
    # Demand parameters
    base_demand_m3 = Column(DECIMAL(12, 2))
    weather_adjustment_factor = Column(DECIMAL(4, 3), default=1.0)
    priority_override = Column(DECIMAL(3, 1))
    
    # Constraints
    min_delivery_m3 = Column(DECIMAL(12, 2))
    max_delivery_m3 = Column(DECIMAL(12, 2))
    delivery_window_hours = Column(Integer, default=168)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    scenario = relationship("Scenario", back_populates="section_demands")


class GateOperation(Base):
    """Scheduled and executed gate operations"""
    __tablename__ = "gate_operations"
    __table_args__ = {"schema": "simulation"}
    
    operation_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("simulation.runs.run_id", ondelete="CASCADE"))
    gate_id = Column(String(50), nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    target_opening_m = Column(DECIMAL(6, 3), nullable=False)
    operation_type = Column(String(20), nullable=False)
    priority = Column(String(20), default="normal")
    
    # Execution tracking
    executed_time = Column(DateTime)
    actual_opening_m = Column(DECIMAL(6, 3))
    execution_duration_minutes = Column(Integer)
    status = Column(String(20), default="scheduled")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    run = relationship("SimulationRun", back_populates="gate_operations")


class OptimizationResult(Base):
    """Results from optimization runs"""
    __tablename__ = "optimization_results"
    __table_args__ = {"schema": "simulation"}
    
    result_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("simulation.runs.run_id", ondelete="CASCADE"))
    optimization_time = Column(DateTime, nullable=False)
    objective_function = Column(String(50), nullable=False)
    
    # Metrics
    water_efficiency_score = Column(DECIMAL(5, 4))
    fairness_index = Column(DECIMAL(5, 4))
    energy_usage_kwh = Column(DECIMAL(10, 2))
    computational_time_ms = Column(Integer)
    iterations = Column(Integer)
    convergence_achieved = Column(Boolean, default=False)
    
    # Solution details
    gate_schedule = Column(JSON, nullable=False)
    section_allocations = Column(JSON, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    run = relationship("SimulationRun", back_populates="optimization_results")


class AnalysisResult(Base):
    """Analysis results from simulation runs"""
    __tablename__ = "analysis_results"
    __table_args__ = {"schema": "simulation"}
    
    analysis_id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("simulation.runs.run_id", ondelete="CASCADE"))
    analysis_type = Column(String(50), nullable=False)
    
    # Metrics
    avg_delivery_efficiency = Column(DECIMAL(5, 4))
    water_shortage_events = Column(Integer, default=0)
    excess_water_events = Column(Integer, default=0)
    unmet_demand_m3 = Column(DECIMAL(15, 2))
    
    # Detailed results
    section_performance = Column(JSON)
    temporal_analysis = Column(JSON)
    recommendations = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    run = relationship("SimulationRun", back_populates="analysis_results")