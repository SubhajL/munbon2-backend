from typing import List, Optional, Dict
from datetime import datetime, date
from pydantic import BaseModel, Field
from enum import Enum
import strawberry


class CoverageTypeEnum(str, Enum):
    FULL_MUNBON = "full_munbon"
    ZONES = "zones"
    SECTIONS = "sections"


class ResultDisplayPeriodEnum(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class AccumulationPeriodEnum(str, Enum):
    NONE = "none"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    SEASONAL = "seasonal"


class DemandDisplayMethodEnum(str, Enum):
    ROS_ONLY = "ros_only"
    RID_MS_ONLY = "rid_ms_only"
    BOTH_SEPARATE = "both_separate"
    COMBINED = "combined"


class MapDefaultViewEnum(str, Enum):
    MUNBON = "munbon"
    ZONES = "zones"
    SECTIONS = "sections"


# Pydantic models for validation
class CropSeasonConfig(BaseModel):
    config_id: Optional[str] = None
    season_name: str = Field(..., min_length=1, max_length=100)
    season_year: int = Field(..., ge=2020, le=2100)
    start_date: date
    end_date: date
    
    # Location selection
    coverage_type: CoverageTypeEnum
    selected_zones: Optional[List[int]] = None
    selected_sections: Optional[List[str]] = None
    
    # Result type periods
    result_display_period: ResultDisplayPeriodEnum
    accumulation_period: AccumulationPeriodEnum
    
    # Water demand display
    demand_display_method: DemandDisplayMethodEnum
    demand_combination_strategy: Optional[str] = "aquacrop_priority"
    
    # Spatial visualization
    map_default_view: MapDefaultViewEnum = MapDefaultViewEnum.ZONES
    map_color_scheme: str = "demand_gradient"
    show_irrigation_channels: bool = True
    show_delivery_gates: bool = True
    
    # Additional settings
    weather_data_source: str = "tmd"
    rainfall_adjustment_enabled: bool = True
    awd_integration_enabled: bool = False
    
    # Metadata
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    is_active: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "season_name": "แผนการเพาะปลูก 2567",
                "season_year": 2024,
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "coverage_type": "zones",
                "selected_zones": [1, 2, 3],
                "result_display_period": "weekly",
                "accumulation_period": "monthly",
                "demand_display_method": "both_separate",
                "map_default_view": "zones"
            }
        }


# GraphQL Types
@strawberry.type
class CropSeasonConfigType:
    config_id: str
    season_name: str
    season_year: int
    start_date: date
    end_date: date
    
    # Location selection
    coverage_type: str
    selected_zones: Optional[List[int]]
    selected_sections: Optional[List[str]]
    
    # Result type periods
    result_display_period: str
    accumulation_period: str
    
    # Water demand display
    demand_display_method: str
    demand_combination_strategy: str
    
    # Spatial visualization
    map_default_view: str
    map_color_scheme: str
    show_irrigation_channels: bool
    show_delivery_gates: bool
    
    # Additional settings
    weather_data_source: str
    rainfall_adjustment_enabled: bool
    awd_integration_enabled: bool
    
    # Metadata
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool


@strawberry.input
class CropSeasonConfigInput:
    season_name: str
    season_year: int
    start_date: date
    end_date: date
    
    # Location selection
    coverage_type: str
    selected_zones: Optional[List[int]] = None
    selected_sections: Optional[List[str]] = None
    
    # Result type periods
    result_display_period: str = "weekly"
    accumulation_period: str = "monthly"
    
    # Water demand display
    demand_display_method: str = "both_separate"
    demand_combination_strategy: Optional[str] = "aquacrop_priority"
    
    # Spatial visualization
    map_default_view: str = "zones"
    map_color_scheme: str = "demand_gradient"
    show_irrigation_channels: bool = True
    show_delivery_gates: bool = True
    
    # Additional settings
    weather_data_source: str = "tmd"
    rainfall_adjustment_enabled: bool = True
    awd_integration_enabled: bool = False


@strawberry.type
class CropSeasonInitResult:
    success: bool
    config_id: str
    message: str
    warnings: Optional[List[str]] = None