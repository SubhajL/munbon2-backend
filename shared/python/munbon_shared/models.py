"""Common data models for Munbon services."""

from typing import Optional, Generic, TypeVar, Any, Dict, List
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, validator


T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""
    
    page: int = Field(default=1, ge=1, description="Page number")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.limit


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""
    
    data: List[T]
    pagination: Dict[str, Any] = Field(
        description="Pagination metadata"
    )
    
    @classmethod
    def create(
        cls,
        data: List[T],
        page: int,
        limit: int,
        total: int
    ) -> "PaginatedResponse[T]":
        """Create paginated response with metadata."""
        total_pages = (total + limit - 1) // limit
        
        return cls(
            data=data,
            pagination={
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        )


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""
    
    success: bool = Field(description="Whether the request was successful")
    data: Optional[T] = Field(default=None, description="Response data")
    error: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Error information"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata"
    )
    
    @classmethod
    def success_response(
        cls,
        data: T,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "ApiResponse[T]":
        """Create a successful response."""
        return cls(
            success=True,
            data=data,
            metadata=metadata
        )
    
    @classmethod
    def error_response(
        cls,
        error_message: str,
        error_code: str,
        status_code: int,
        details: Optional[Dict[str, Any]] = None
    ) -> "ApiResponse[None]":
        """Create an error response."""
        return cls(
            success=False,
            error={
                "message": error_message,
                "code": error_code,
                "status_code": status_code,
                "details": details,
                "timestamp": datetime.utcnow().isoformat()
            }
        )


class HealthStatus(str, Enum):
    """Health check status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class HealthCheckResponse(BaseModel):
    """Health check response model."""
    
    status: HealthStatus
    service: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    checks: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description="Individual health check results"
    )


class UserRole(str, Enum):
    """User roles in the system."""
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"
    SYSTEM = "SYSTEM"


class User(BaseModel):
    """User model."""
    
    id: str
    email: str
    name: str
    role: UserRole
    permissions: List[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class DataQuality(str, Enum):
    """Data quality indicators."""
    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class SensorReading(BaseModel):
    """Sensor reading data model."""
    
    sensor_id: str = Field(description="Unique sensor identifier")
    timestamp: datetime = Field(description="Reading timestamp")
    value: float = Field(description="Sensor value")
    unit: str = Field(description="Unit of measurement")
    quality: DataQuality = Field(
        default=DataQuality.GOOD,
        description="Data quality indicator"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata"
    )
    
    @validator("sensor_id")
    def validate_sensor_id(cls, v: str) -> str:
        """Validate sensor ID format."""
        if not v.startswith("SENSOR-"):
            raise ValueError("Sensor ID must start with 'SENSOR-'")
        return v


class GateStatus(str, Enum):
    """Gate operational status."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    OPENING = "OPENING"
    CLOSING = "CLOSING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class GateControl(BaseModel):
    """Gate control data model."""
    
    gate_id: str = Field(description="Unique gate identifier")
    position: float = Field(
        ge=0,
        le=100,
        description="Current position (0-100%)"
    )
    target_position: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Target position (0-100%)"
    )
    status: GateStatus = Field(description="Current gate status")
    last_updated: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )
    operator: Optional[str] = Field(
        default=None,
        description="Operator who made the last change"
    )
    
    @validator("gate_id")
    def validate_gate_id(cls, v: str) -> str:
        """Validate gate ID format."""
        if not v.startswith("GATE-"):
            raise ValueError("Gate ID must start with 'GATE-'")
        return v