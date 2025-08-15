"""
Database models for weekly weather adjustments.

These models store accumulated weather-based adjustments
that affect next week's irrigation schedule generation.
"""

from sqlalchemy import (
    Column, String, Float, Boolean, Integer, Date, DateTime,
    JSON, UniqueConstraint, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from .base import Base


class WeeklyWeatherAdjustment(Base):
    """
    Stores daily weather adjustments that accumulate to affect next week's schedule.
    
    These are NOT real-time operational changes, but factors that influence
    water demand calculations when generating the following week's irrigation schedule.
    """
    __tablename__ = "weekly_weather_adjustments"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Zone and time identification
    zone_id = Column(String(50), nullable=False, index=True)
    adjustment_date = Column(Date, nullable=False)
    week_number = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    
    # Adjustment factors (cumulative for the day)
    demand_reduction_percent = Column(
        Float, 
        default=0.0,
        comment="Percentage reduction in water demand (0-100)"
    )
    operations_cancelled = Column(
        Boolean, 
        default=False,
        comment="Whether operations should be cancelled for this zone/date"
    )
    et_adjustment_percent = Column(
        Float, 
        default=0.0,
        comment="ET adjustment percentage (-100 to +100)"
    )
    application_time_increase_percent = Column(
        Float, 
        default=0.0,
        comment="Increase in application time due to wind (0-100)"
    )
    
    # Weather data that triggered adjustments
    rainfall_mm = Column(Float, nullable=True)
    temperature_drop_celsius = Column(Float, nullable=True)
    wind_speed_kmh = Column(Float, nullable=True)
    
    # Detailed factors
    adjustment_factors = Column(
        JSON, 
        default=list,
        comment="List of adjustment factors with reasons"
    )
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    processed_by = Column(String(100), nullable=True)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('zone_id', 'adjustment_date', name='uq_zone_date'),
        Index('idx_week_year', 'week_number', 'year'),
        Index('idx_zone_week', 'zone_id', 'week_number', 'year'),
        CheckConstraint('demand_reduction_percent >= 0 AND demand_reduction_percent <= 100'),
        CheckConstraint('et_adjustment_percent >= -100 AND et_adjustment_percent <= 100'),
        CheckConstraint('application_time_increase_percent >= 0'),
        CheckConstraint('week_number >= 1 AND week_number <= 53'),
        CheckConstraint('year >= 2024'),
    )
    
    def __repr__(self):
        return (
            f"<WeeklyWeatherAdjustment("
            f"zone={self.zone_id}, "
            f"date={self.adjustment_date}, "
            f"reduction={self.demand_reduction_percent}%"
            f")>"
        )
    
    @property
    def has_significant_impact(self) -> bool:
        """Check if this adjustment has significant impact"""
        return (
            self.demand_reduction_percent > 10 or
            self.operations_cancelled or
            abs(self.et_adjustment_percent) > 10 or
            self.application_time_increase_percent > 10
        )
    
    @property
    def total_demand_modifier(self) -> float:
        """Calculate total demand modifier (multiplicative factor)"""
        if self.operations_cancelled:
            return 0.0
        return (100 - self.demand_reduction_percent) / 100


class WeeklyAdjustmentSummary(Base):
    """
    Summary of weekly adjustments for reporting and analysis.
    Generated at the end of each week for zone manager reports.
    """
    __tablename__ = "weekly_adjustment_summaries"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Week identification
    week_number = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    
    # Summary data
    zones_affected = Column(Integer, default=0)
    total_zones = Column(Integer, nullable=False)
    
    # Aggregate adjustments
    average_demand_reduction_percent = Column(Float, default=0.0)
    zones_with_cancelled_operations = Column(Integer, default=0)
    total_cancelled_operation_days = Column(Integer, default=0)
    
    # Weather summary
    total_rainfall_mm = Column(Float, default=0.0)
    max_daily_rainfall_mm = Column(Float, default=0.0)
    days_with_rainfall = Column(Integer, default=0)
    average_temperature_drop = Column(Float, nullable=True)
    max_wind_speed_kmh = Column(Float, nullable=True)
    
    # Impact on next week
    estimated_water_savings_m3 = Column(Float, nullable=True)
    estimated_schedule_changes = Column(Integer, nullable=True)
    
    # Report data
    report_generated_at = Column(DateTime, nullable=True)
    report_sent_to_zones = Column(Boolean, default=False)
    zone_manager_acknowledgments = Column(JSON, default=dict)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    generated_by = Column(String(100), nullable=True)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('week_number', 'year', name='uq_week_summary'),
        Index('idx_summary_year', 'year'),
        CheckConstraint('week_number >= 1 AND week_number <= 53'),
        CheckConstraint('year >= 2024'),
    )
    
    def __repr__(self):
        return (
            f"<WeeklyAdjustmentSummary("
            f"week={self.week_number}, "
            f"year={self.year}, "
            f"zones_affected={self.zones_affected}"
            f")>"
        )


class AdjustmentRule(Base):
    """
    Configurable rules for weather-based adjustments.
    Allows dynamic configuration of thresholds and impacts.
    """
    __tablename__ = "adjustment_rules"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Rule identification
    rule_code = Column(String(50), unique=True, nullable=False)
    rule_name = Column(String(200), nullable=False)
    rule_type = Column(String(50), nullable=False)  # rainfall, temperature, wind, etc.
    
    # Conditions
    condition_field = Column(String(100), nullable=False)  # e.g., "rainfall_mm"
    condition_operator = Column(String(10), nullable=False)  # >, <, >=, <=, ==
    condition_value = Column(Float, nullable=False)
    
    # Additional conditions (AND logic)
    additional_conditions = Column(JSON, nullable=True)
    
    # Actions
    action_type = Column(String(50), nullable=False)  # reduce_demand, cancel_ops, etc.
    action_value = Column(Float, nullable=False)  # percentage or absolute value
    action_unit = Column(String(20), nullable=False)  # percent, hours, etc.
    
    # Applicability
    applicable_zones = Column(JSON, nullable=True)  # null = all zones
    applicable_crops = Column(JSON, nullable=True)  # null = all crops
    applicable_months = Column(JSON, nullable=True)  # null = all months
    
    # Priority and conflicts
    priority = Column(Integer, default=100)  # Higher number = higher priority
    conflicts_with = Column(JSON, nullable=True)  # List of rule codes
    
    # Status
    active = Column(Boolean, default=True)
    effective_from = Column(Date, nullable=True)
    effective_until = Column(Date, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    created_by = Column(String(100), nullable=True)
    approved_by = Column(String(100), nullable=True)
    
    # Constraints
    __table_args__ = (
        Index('idx_rule_type_active', 'rule_type', 'active'),
        CheckConstraint("condition_operator IN ('>', '<', '>=', '<=', '==', '!=')"),
        CheckConstraint("action_type IN ('reduce_demand', 'cancel_operations', 'adjust_et', 'increase_time')"),
    )
    
    def __repr__(self):
        return (
            f"<AdjustmentRule("
            f"code={self.rule_code}, "
            f"condition={self.condition_field}{self.condition_operator}{self.condition_value}, "
            f"action={self.action_type}:{self.action_value}{self.action_unit}"
            f")>"
        )
    
    def evaluate(self, data: dict) -> bool:
        """Evaluate if rule conditions are met"""
        if self.condition_field not in data:
            return False
        
        value = data[self.condition_field]
        threshold = self.condition_value
        
        operators = {
            '>': lambda x, y: x > y,
            '<': lambda x, y: x < y,
            '>=': lambda x, y: x >= y,
            '<=': lambda x, y: x <= y,
            '==': lambda x, y: x == y,
            '!=': lambda x, y: x != y,
        }
        
        if not operators[self.condition_operator](value, threshold):
            return False
        
        # Check additional conditions
        if self.additional_conditions:
            for cond in self.additional_conditions:
                field = cond.get('field')
                op = cond.get('operator')
                val = cond.get('value')
                
                if field in data and not operators[op](data[field], val):
                    return False
        
        return True