"""
Pydantic schemas for the scheduler service.
"""

# Schedule schemas
from .schedule import (
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    ScheduleSummary,
    ScheduleGenerateRequest,
)

# Operation schemas
from .operation import (
    OperationBase,
    OperationCreate,
    OperationUpdate,
    OperationResponse,
    OperationSummary,
    OperationStatus,
    OperationStatusEnum,
    OperationType,
    OperationPriority,
    GateOperationHistory,
    OperationBatch,
    OperationPerformance,
    GpsCoordinates,
)

# Team schemas
from .team import (
    TeamBase,
    TeamCreate,
    TeamUpdate,
    TeamResponse,
    TeamSummary,
    TeamStatus,
    TeamCapability,
    TeamLocation,
    TeamLocationUpdate,
    TeamMember,
    TeamAvailability,
    TeamInstructions,
    TeamPerformance,
    VehicleType,
)

# Monitoring schemas
from .monitoring import (
    ScheduleStatus,
    OperationProgress,
    TeamProgress,
    MonitoringAlert,
    AlertLevel,
    AlertType,
    PerformanceMetric,
    MetricType,
    SystemHealth,
    RealtimeUpdate,
    DashboardSummary,
    HistoricalComparison,
    AlertConfiguration,
)

# Adaptation schemas
from .adaptation import (
    AdaptationType,
    FailureType,
    AdaptationStrategy,
    WeatherChangeType,
    DemandUrgency,
    GateFailureRequest,
    WeatherChangeRequest,
    DemandChangeRequest,
    TeamUnavailableRequest,
    ReoptimizationRequest,
    AdaptationResponse,
    AdaptationSummary,
    ContingencyPlan,
    AdaptationMetrics,
)

# Demand schemas
from .demands import (
    SectionDemand,
    DemandSubmission,
    DemandConflict,
    DemandValidationResult,
    DemandResponse,
    AggregatedDemands,
    DemandProcessingStatus,
)

# Field operation schemas
from .field_ops import (
    FieldInstruction,
    GateOperation,
    TeamLocation,
    PhotoUpload,
    RouteOptimization,
    OfflineDataPackage,
    SyncData,
)

__all__ = [
    # Schedule
    "ScheduleCreate",
    "ScheduleUpdate",
    "ScheduleResponse",
    "ScheduleSummary",
    "ScheduleGenerateRequest",
    # Operation
    "OperationBase",
    "OperationCreate",
    "OperationUpdate",
    "OperationResponse",
    "OperationSummary",
    "OperationStatus",
    "OperationStatusEnum",
    "OperationType",
    "OperationPriority",
    "GateOperationHistory",
    "OperationBatch",
    "OperationPerformance",
    "GpsCoordinates",
    # Team
    "TeamBase",
    "TeamCreate",
    "TeamUpdate",
    "TeamResponse",
    "TeamSummary",
    "TeamStatus",
    "TeamCapability",
    "TeamLocation",
    "TeamLocationUpdate",
    "TeamMember",
    "TeamAvailability",
    "TeamInstructions",
    "TeamPerformance",
    "VehicleType",
    # Monitoring
    "ScheduleStatus",
    "OperationProgress",
    "TeamProgress",
    "MonitoringAlert",
    "AlertLevel",
    "AlertType",
    "PerformanceMetric",
    "MetricType",
    "SystemHealth",
    "RealtimeUpdate",
    "DashboardSummary",
    "HistoricalComparison",
    "AlertConfiguration",
    # Adaptation
    "AdaptationType",
    "FailureType",
    "AdaptationStrategy",
    "WeatherChangeType",
    "DemandUrgency",
    "GateFailureRequest",
    "WeatherChangeRequest",
    "DemandChangeRequest",
    "TeamUnavailableRequest",
    "ReoptimizationRequest",
    "AdaptationResponse",
    "AdaptationSummary",
    "ContingencyPlan",
    "AdaptationMetrics",
    # Demand
    "SectionDemand",
    "DemandSubmission",
    "DemandConflict",
    "DemandValidationResult",
    "DemandResponse",
    "AggregatedDemands",
    "DemandProcessingStatus",
    # Field ops
    "FieldInstruction",
    "GateOperation",
    "TeamLocation",
    "PhotoUpload",
    "RouteOptimization",
    "OfflineDataPackage",
    "SyncData",
]