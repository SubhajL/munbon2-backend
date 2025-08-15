"""
Monitoring schemas for the scheduler service.

These schemas define real-time monitoring data structures,
including progress tracking, alerts, and system status.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date, time
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field, validator


class AlertLevel(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of monitoring alerts"""
    OPERATION_DELAYED = "operation_delayed"
    OPERATION_FAILED = "operation_failed"
    GATE_MALFUNCTION = "gate_malfunction"
    FLOW_DEVIATION = "flow_deviation"
    TEAM_UNAVAILABLE = "team_unavailable"
    WEATHER_CHANGE = "weather_change"
    DEMAND_SPIKE = "demand_spike"
    SCHEDULE_CONFLICT = "schedule_conflict"
    SAFETY_ISSUE = "safety_issue"
    COMMUNICATION_LOST = "communication_lost"


class MetricType(str, Enum):
    """Types of performance metrics"""
    COMPLETION_RATE = "completion_rate"
    ON_TIME_RATE = "on_time_rate"
    FLOW_ACCURACY = "flow_accuracy"
    WATER_DELIVERED = "water_delivered"
    TRAVEL_EFFICIENCY = "travel_efficiency"
    TEAM_UTILIZATION = "team_utilization"


class ScheduleStatus(BaseModel):
    """Overall schedule execution status"""
    schedule_id: UUID
    schedule_code: str
    week_number: int
    year: int
    status: str  # active, completed, suspended
    start_date: date
    end_date: date
    
    # Progress
    total_operations: int
    completed_operations: int
    failed_operations: int
    in_progress_operations: int
    scheduled_operations: int
    
    # Performance
    completion_percentage: float = Field(..., ge=0, le=100)
    on_time_percentage: float = Field(..., ge=0, le=100)
    
    # Water delivery
    planned_water_m3: float
    delivered_water_m3: float
    delivery_percentage: float = Field(..., ge=0, le=100)
    
    # Teams
    active_teams: int
    total_teams: int
    
    # Time info
    current_server_time: datetime
    last_update: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class OperationProgress(BaseModel):
    """Real-time operation progress"""
    operation_id: UUID
    gate_id: str
    gate_name: str
    team_id: str
    team_name: str
    
    # Status
    status: str
    started_at: Optional[datetime]
    expected_completion: Optional[datetime]
    actual_completion: Optional[datetime]
    
    # Progress
    progress_percentage: float = Field(..., ge=0, le=100)
    elapsed_minutes: Optional[int]
    remaining_minutes: Optional[int]
    
    # Performance
    is_delayed: bool = False
    delay_minutes: Optional[int]
    delay_reason: Optional[str]
    
    # Location
    team_location: Optional[Dict[str, float]]
    gate_location: Dict[str, float]
    distance_remaining_km: Optional[float]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            UUID: lambda v: str(v),
        }


class TeamProgress(BaseModel):
    """Team progress summary"""
    team_id: UUID
    team_code: str
    team_name: str
    status: str
    
    # Current operation
    current_operation_id: Optional[UUID]
    current_gate: Optional[str]
    current_location: Optional[Dict[str, float]]
    
    # Daily progress
    operations_completed: int
    operations_remaining: int
    total_operations: int
    
    # Time tracking
    work_start_time: Optional[datetime]
    estimated_finish_time: Optional[datetime]
    overtime_minutes: int = 0
    
    # Performance
    on_time_rate_today: float = Field(..., ge=0, le=100)
    average_operation_time: Optional[float]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
            UUID: lambda v: str(v),
        }


class MonitoringAlert(BaseModel):
    """Real-time monitoring alert"""
    id: UUID
    alert_type: AlertType
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime
    
    # Context
    schedule_id: Optional[UUID]
    operation_id: Optional[UUID]
    gate_id: Optional[str]
    team_id: Optional[UUID]
    
    # Location
    location: Optional[Dict[str, Any]]
    affected_zones: List[str] = Field(default_factory=list)
    
    # Actions
    recommended_action: Optional[str]
    auto_resolved: bool = False
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]
    resolution_notes: Optional[str]
    
    # Impact
    estimated_impact: Optional[Dict[str, Any]]
    affected_operations: List[UUID] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class PerformanceMetric(BaseModel):
    """Performance metric data point"""
    metric_type: MetricType
    value: float
    unit: str
    timestamp: datetime
    
    # Context
    schedule_id: Optional[UUID]
    team_id: Optional[UUID]
    gate_id: Optional[str]
    zone_id: Optional[str]
    
    # Comparison
    target_value: Optional[float]
    previous_value: Optional[float]
    change_percentage: Optional[float]
    
    # Threshold
    is_below_threshold: bool = False
    threshold_value: Optional[float]
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class SystemHealth(BaseModel):
    """System health status"""
    timestamp: datetime
    overall_status: str = Field(..., description="healthy, degraded, critical")
    
    # Service health
    scheduler_service: Dict[str, Any]
    database_status: Dict[str, Any]
    redis_status: Dict[str, Any]
    
    # External services
    ros_service: Dict[str, Any]
    gis_service: Dict[str, Any]
    flow_monitoring_service: Dict[str, Any]
    
    # Resources
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    
    # Activity
    active_connections: int
    requests_per_minute: float
    average_response_time_ms: float
    
    # Queues
    pending_operations: int
    pending_adaptations: int
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class RealtimeUpdate(BaseModel):
    """WebSocket real-time update message"""
    update_type: str = Field(..., description="Type of update")
    timestamp: datetime
    data: Dict[str, Any]
    
    # Targeting
    broadcast: bool = Field(True, description="Broadcast to all or specific clients")
    target_teams: List[str] = Field(default_factory=list)
    target_zones: List[str] = Field(default_factory=list)
    
    # Priority
    priority: str = Field("normal", description="high, normal, low")
    requires_acknowledgment: bool = False
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class DashboardSummary(BaseModel):
    """Dashboard summary data"""
    timestamp: datetime
    schedule_status: ScheduleStatus
    
    # Current activity
    active_operations: List[OperationProgress]
    active_teams: List[TeamProgress]
    recent_alerts: List[MonitoringAlert]
    
    # Performance metrics
    key_metrics: List[PerformanceMetric]
    
    # Predictions
    estimated_completion_time: datetime
    potential_delays: List[Dict[str, Any]]
    
    # Resources
    water_delivered_today_m3: float
    water_remaining_today_m3: float
    gates_operated_today: int
    total_travel_distance_km: float
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
        }


class HistoricalComparison(BaseModel):
    """Historical performance comparison"""
    current_week: Dict[str, Any]
    previous_week: Optional[Dict[str, Any]]
    same_week_last_year: Optional[Dict[str, Any]]
    
    # Trends
    completion_rate_trend: List[float]
    on_time_rate_trend: List[float]
    water_efficiency_trend: List[float]
    
    # Insights
    improvements: List[str]
    degradations: List[str]
    recommendations: List[str]


class AlertConfiguration(BaseModel):
    """Alert configuration settings"""
    alert_type: AlertType
    enabled: bool = True
    
    # Thresholds
    threshold_value: Optional[float]
    threshold_unit: Optional[str]
    comparison_operator: str = Field("greater_than", description="greater_than, less_than, equals")
    
    # Timing
    evaluation_interval_minutes: int = Field(5, ge=1, le=60)
    cooldown_minutes: int = Field(30, ge=0, description="Prevent alert spam")
    
    # Notification
    notification_channels: List[str] = Field(default_factory=list)
    escalation_after_minutes: Optional[int]
    
    # Recipients
    notify_teams: List[str] = Field(default_factory=list)
    notify_roles: List[str] = Field(default_factory=list)
    
    class Config:
        use_enum_values = True