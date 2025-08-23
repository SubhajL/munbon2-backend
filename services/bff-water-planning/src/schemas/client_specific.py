import strawberry
from typing import List, Optional
from datetime import datetime


# Mobile-specific types (lightweight)
@strawberry.type
class MobileSectionType:
    """Lightweight section data for mobile clients"""
    id: str
    name: str
    zone_code: str
    area_rai: float
    current_demand_m3: Optional[float] = None
    awd_active: bool = False
    
    
@strawberry.type
class MobileDemandSummary:
    """Simplified demand summary for mobile"""
    total_demand_m3: float
    sections_count: int
    priority: str
    status: str


@strawberry.type
class MobileWaterDashboard:
    """Mobile-optimized dashboard data"""
    zone_name: str
    total_demand: float
    awd_active: bool
    last_updated: datetime
    sections: List[MobileSectionType]
    alerts_count: int


# Web-specific types (full detail)
@strawberry.type
class WebSectionType:
    """Full section data for web clients"""
    id: str
    name: str
    zone_code: str
    area_rai: float
    plot_count: int
    geometry: Optional[str] = None  # GeoJSON
    current_demand_m3: Optional[float] = None
    demand_trend: Optional[List[float]] = None
    awd_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime


@strawberry.type
class ChartDataset:
    """Chart dataset for web visualizations"""
    label: str
    data: List[float]
    borderColor: Optional[str] = None
    backgroundColor: Optional[str] = None


@strawberry.type
class ChartData:
    """Chart data structure for web UI"""
    labels: List[str]
    datasets: List[ChartDataset]


@strawberry.type
class WebDemandDetails:
    """Detailed demand information for web"""
    section_id: str
    gross_demand_m3: float
    effective_rainfall_m3: float
    net_demand_m3: float
    method: str
    priority_score: float
    priority_factors: Optional[dict] = None


@strawberry.type
class WebWaterDashboard:
    """Web dashboard with full analytics"""
    zone: dict  # Full zone data
    demand_details: List[WebDemandDetails]
    awd_full_status: Optional[dict] = None
    charts: Optional[ChartData] = None
    historical_data: Optional[List[dict]] = None
    predictions: Optional[List[dict]] = None
    performance_metrics: Optional[dict] = None


# API-specific types (structured)
@strawberry.type
class APIResponse:
    """Standard API response wrapper"""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    timestamp: datetime = strawberry.field(default_factory=datetime.utcnow)
    
    
@strawberry.type
class APIDemandData:
    """Structured demand data for API clients"""
    level_type: str
    level_id: str
    demand_date: str
    gross_demand_m3: float
    net_demand_m3: float
    method: str
    metadata: Optional[dict] = None