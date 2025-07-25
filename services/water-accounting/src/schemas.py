"""Pydantic schemas for API responses"""

from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

class SectionInfo(BaseModel):
    id: str
    name: str
    area_hectares: float
    primary_crop: Optional[str]
    crop_stage: Optional[str]

class SectionMetricsResponse(BaseModel):
    total_delivered_m3: float
    total_losses_m3: float
    delivery_efficiency: float
    application_efficiency: float
    overall_efficiency: float
    current_deficit_m3: float

class RecentDelivery(BaseModel):
    delivery_id: str
    scheduled_start: str
    actual_start: Optional[str]
    status: str
    gate_outflow_m3: float
    section_inflow_m3: float
    transit_loss_m3: float

class DeficitStatus(BaseModel):
    has_deficit: bool
    deficit_m3: float
    stress_level: str
    weeks_in_deficit: int

class SectionAccountingResponse(BaseModel):
    section: SectionInfo
    current_metrics: Optional[SectionMetricsResponse]
    recent_deliveries: List[RecentDelivery]
    deficit_status: Optional[DeficitStatus]

class EfficiencyReportSummary(BaseModel):
    avg_delivery_efficiency: float
    avg_application_efficiency: float
    avg_overall_efficiency: float
    total_water_delivered_m3: float
    total_water_consumed_m3: float
    total_losses_m3: float

class PerformanceDistribution(BaseModel):
    excellent: Dict[str, float]
    good: Dict[str, float]
    fair: Dict[str, float]
    poor: Dict[str, float]
    very_poor: Dict[str, float]

class SectionPerformance(BaseModel):
    section_id: str
    section_name: str
    performance_score: float
    overall_efficiency: float
    limiting_factor: Optional[str]

class Recommendation(BaseModel):
    type: str
    priority: str
    area: str
    recommendation: str
    potential_improvement: Optional[str]
    sections: Optional[List[str]]

class EfficiencyReportResponse(BaseModel):
    report_id: str
    report_period: Dict[str, str]
    zone_id: Optional[str]
    total_sections: int
    summary_statistics: EfficiencyReportSummary
    performance_distribution: PerformanceDistribution
    best_performers: List[SectionPerformance]
    worst_performers: List[SectionPerformance]
    recommendations: List[Recommendation]
    generated_at: str