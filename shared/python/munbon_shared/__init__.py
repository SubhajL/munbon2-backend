"""Munbon shared utilities for Python microservices."""

from munbon_shared.config import Config, get_config
from munbon_shared.errors import (
    BaseError,
    ValidationError,
    NotFoundError,
    UnauthorizedError,
    ForbiddenError,
    ConflictError,
    RateLimitError,
    ServiceUnavailableError,
)
from munbon_shared.logging import get_logger, configure_logging
from munbon_shared.middleware import (
    error_handler,
    request_logger,
    request_id_middleware,
    rate_limit_middleware,
)
from munbon_shared.models import (
    PaginationParams,
    PaginatedResponse,
    ApiResponse,
    HealthCheckResponse,
    User,
    UserRole,
    SensorReading,
    DataQuality,
    GateControl,
    GateStatus,
)
from munbon_shared.utils import (
    retry_async,
    CircuitBreaker,
    SimpleCache,
)

__all__ = [
    # Config
    "Config",
    "get_config",
    # Errors
    "BaseError",
    "ValidationError",
    "NotFoundError",
    "UnauthorizedError",
    "ForbiddenError",
    "ConflictError",
    "RateLimitError",
    "ServiceUnavailableError",
    # Logging
    "get_logger",
    "configure_logging",
    # Middleware
    "error_handler",
    "request_logger",
    "request_id_middleware",
    "rate_limit_middleware",
    # Models
    "PaginationParams",
    "PaginatedResponse",
    "ApiResponse",
    "HealthCheckResponse",
    "User",
    "UserRole",
    "SensorReading",
    "DataQuality",
    "GateControl",
    "GateStatus",
    # Utils
    "retry_async",
    "CircuitBreaker",
    "SimpleCache",
]

__version__ = "1.0.0"