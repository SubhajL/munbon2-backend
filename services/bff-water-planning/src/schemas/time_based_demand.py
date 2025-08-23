from typing import List, Optional, Dict
from datetime import datetime, date
from pydantic import BaseModel, Field
from enum import Enum
import strawberry


class TimePeriodEnum(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    SEASONAL = "seasonal"


class CalculationMethodEnum(str, Enum):
    ROS = "ros"
    RID_MS = "rid_ms"
    AWD = "awd"
    COMBINED = "combined"


# GraphQL Types
@strawberry.type
class DailyDemandType:
    """Daily water demand data"""
    date: date
    plot_id: str
    section_id: str
    zone: int
    
    # Demand values
    ros_demand_m3: float
    rid_ms_demand_m3: float  # aquacrop_demand_m3 in DB
    awd_demand_m3: float
    combined_demand_m3: float  # This now contains water-level-adjusted value
    selected_method: str
    
    # Additional info
    crop_type: Optional[str]
    growth_stage: Optional[str]
    area_rai: float
    stress_level: Optional[str]
    
    # Water level adjustment fields
    original_demand_m3: Optional[float] = None
    adjusted_demand_m3: Optional[float] = None
    water_level_m: Optional[float] = None
    adjustment_factor: float = 1.0
    adjustment_method: Optional[str] = None
    water_level_data_quality: Optional[float] = None


@strawberry.type
class AccumulatedDemandType:
    """Accumulated water demand over a period"""
    section_id: str
    control_interval: str  # weekly, biweekly, monthly
    start_date: date
    end_date: date
    
    # Accumulated values
    total_demand_m3: float
    plot_count: int
    avg_daily_demand_m3: float
    peak_daily_demand_m3: float
    
    # Breakdown by method
    total_ros_m3: Optional[float]
    total_rid_ms_m3: Optional[float]
    total_awd_m3: Optional[float]
    
    # Delivery info
    delivery_gate: Optional[str]
    irrigation_channel: Optional[str]
    schedule_id: Optional[str]


@strawberry.type
class DemandComparisonType:
    """Comparison between ROS, RID-MS, and AWD methods"""
    section_id: str
    period: str
    start_date: date
    end_date: date
    
    # ROS data
    ros_total_m3: float
    ros_daily_avg_m3: float
    ros_peak_m3: float
    
    # RID-MS data
    rid_ms_total_m3: float
    rid_ms_daily_avg_m3: float
    rid_ms_peak_m3: float
    
    # AWD data
    awd_total_m3: float
    awd_daily_avg_m3: float
    awd_peak_m3: float
    awd_water_savings_percent: float
    
    # Comparison metrics
    difference_m3: float
    difference_percent: float
    recommended_method: str
    recommendation_reason: str


@strawberry.type
class SeasonalDemandSummaryType:
    """Seasonal water demand summary"""
    season_config_id: str
    season_name: str
    total_area_rai: float
    total_plots: int
    
    # Season totals
    total_demand_m3: float
    total_ros_m3: float
    total_rid_ms_m3: float
    total_awd_m3: float
    
    # Monthly breakdown
    monthly_demands: List['MonthlyDemandType']
    
    # Peak periods
    peak_month: str
    peak_demand_m3: float
    
    # Efficiency metrics
    avg_demand_per_rai: float
    water_use_efficiency: float


@strawberry.type
class MonthlyDemandType:
    """Monthly demand data"""
    month: str  # YYYY-MM
    total_demand_m3: float
    ros_demand_m3: float
    rid_ms_demand_m3: float
    awd_demand_m3: float
    plot_count: int
    avg_daily_m3: float


@strawberry.type
class SpatialDemandType:
    """Spatial water demand data for map visualization"""
    feature_id: str  # section_id or zone_id
    feature_type: str  # 'section' or 'zone'
    geometry: Optional[Dict]  # GeoJSON geometry
    
    # Current demand
    current_demand_m3: float
    demand_per_rai: float
    
    # Demand by method
    ros_demand_m3: float
    rid_ms_demand_m3: float
    awd_demand_m3: float
    
    # Visual properties
    color_value: float  # 0-1 for gradient coloring
    label: str
    
    # Additional info
    area_rai: float
    crop_diversity: int  # Number of different crops
    priority_score: Optional[float]


@strawberry.type
class DemandTimeSeriesType:
    """Time series data for demand charts"""
    section_id: str
    dates: List[date]
    ros_values: List[float]
    rid_ms_values: List[float]
    awd_values: List[float]
    combined_values: List[float]
    
    # Statistics
    trend: str  # 'increasing', 'decreasing', 'stable'
    avg_demand: float
    std_deviation: float


@strawberry.type
class AWDDemandType:
    """AWD-specific water demand data with savings information"""
    section_id: str
    date: date
    
    # Standard demand vs AWD demand
    standard_demand_m3: float
    awd_demand_m3: float
    water_saved_m3: float
    savings_percent: float
    
    # AWD parameters
    irrigation_interval_days: int
    ponding_depth_cm: float
    soil_moisture_threshold: float
    
    # AWD status
    awd_enabled: bool
    irrigation_scheduled: bool
    next_irrigation_date: Optional[date]
    
    # Crop impact
    yield_impact_percent: float
    stress_level: str  # 'none', 'mild', 'moderate', 'severe'