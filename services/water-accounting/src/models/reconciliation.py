"""Reconciliation tracking models"""

from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..database import Base

class ReconciliationStatus(enum.Enum):
    """Status of reconciliation process"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    APPROVED = "approved"
    DISPUTED = "disputed"

class ReconciliationLog(Base):
    """Weekly reconciliation records"""
    __tablename__ = "reconciliation_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    reconciliation_id = Column(String, unique=True, nullable=False)
    
    # Time period
    week_number = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Scope
    zone_id = Column(String)
    section_ids = Column(JSON)  # List of sections reconciled
    
    # Data sources
    auto_data_count = Column(Integer, default=0)  # Automated gate readings
    manual_data_count = Column(Integer, default=0)  # Manual readings
    missing_data_count = Column(Integer, default=0)  # Missing readings
    
    # Volume reconciliation
    total_gate_outflow_m3 = Column(Float)  # Sum of all gate releases
    total_section_inflow_m3 = Column(Float)  # Sum of section receipts
    total_losses_m3 = Column(Float)  # Calculated losses
    unaccounted_volume_m3 = Column(Float)  # Discrepancy
    
    # Manual adjustments
    manual_corrections = Column(JSON)  # List of corrections made
    adjustment_volume_m3 = Column(Float, default=0.0)
    adjustment_reason = Column(String)
    
    # Confidence metrics
    data_quality_score = Column(Float)  # 0-1 overall quality
    confidence_level = Column(Float)  # Statistical confidence
    
    # Status tracking
    status = Column(Enum(ReconciliationStatus), default=ReconciliationStatus.PENDING)
    reconciled_by = Column(String)  # User who performed reconciliation
    approved_by = Column(String)  # Supervisor approval
    
    # Timestamps
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    approved_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Detailed data
    reconciliation_data = Column(JSON)  # Full reconciliation details
    discrepancy_analysis = Column(JSON)  # Analysis of discrepancies
    
    # Notes and issues
    notes = Column(String)
    issues_found = Column(JSON)  # List of issues identified
    actions_required = Column(JSON)  # Follow-up actions


class ReconciliationDetail(Base):
    """Detailed line items for reconciliation"""
    __tablename__ = "reconciliation_details"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    reconciliation_id = Column(String, ForeignKey("reconciliation_logs.reconciliation_id"), nullable=False)
    
    # Section details
    section_id = Column(String, ForeignKey("sections.id"), nullable=False)
    delivery_id = Column(String)
    
    # Original values
    original_gate_outflow_m3 = Column(Float)
    original_section_inflow_m3 = Column(Float)
    original_loss_m3 = Column(Float)
    
    # Reconciled values
    reconciled_gate_outflow_m3 = Column(Float)
    reconciled_section_inflow_m3 = Column(Float)
    reconciled_loss_m3 = Column(Float)
    
    # Adjustments
    adjustment_type = Column(String)  # meter_error, estimation, field_report
    adjustment_value_m3 = Column(Float)
    adjustment_confidence = Column(Float)  # 0-1
    
    # Data source
    data_source = Column(String)  # automated, manual, estimated
    data_quality = Column(String)  # good, fair, poor
    
    # Validation
    validated = Column(Boolean, default=False)
    validation_method = Column(String)
    validation_notes = Column(String)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())