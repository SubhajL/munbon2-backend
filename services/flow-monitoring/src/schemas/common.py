from datetime import datetime
from typing import Optional, Any, Dict, List, Generic, TypeVar
from pydantic import BaseModel, Field
from pydantic.generics import GenericModel

T = TypeVar('T')


class PaginationParams(BaseModel):
    """Common pagination parameters"""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=50, ge=1, le=1000, description="Items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries"""
        return (self.page - 1) * self.page_size


class TimeRange(BaseModel):
    """Time range for queries"""
    start_time: datetime
    end_time: datetime
    
    def validate_range(self) -> None:
        """Validate time range"""
        if self.start_time >= self.end_time:
            raise ValueError("Start time must be before end time")
        
        # Check if range is not too large (e.g., max 1 year)
        delta = self.end_time - self.start_time
        if delta.days > 365:
            raise ValueError("Time range cannot exceed 1 year")


class APIResponse(GenericModel, Generic[T]):
    """Standard API response wrapper"""
    success: bool = Field(default=True)
    data: Optional[T] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @classmethod
    def success_response(
        cls,
        data: T,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "APIResponse[T]":
        """Create a success response"""
        return cls(
            success=True,
            data=data,
            message=message,
            metadata=metadata
        )
    
    @classmethod
    def error_response(
        cls,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "APIResponse[None]":
        """Create an error response"""
        return cls(
            success=False,
            data=None,
            message=message,
            metadata=metadata
        )


class PaginatedResponse(GenericModel, Generic[T]):
    """Paginated response wrapper"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool
    
    @classmethod
    def from_query(
        cls,
        items: List[T],
        total: int,
        pagination: PaginationParams
    ) -> "PaginatedResponse[T]":
        """Create paginated response from query results"""
        total_pages = (total + pagination.page_size - 1) // pagination.page_size
        
        return cls(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
            has_next=pagination.page < total_pages,
            has_previous=pagination.page > 1
        )


class ErrorResponse(BaseModel):
    """Error response schema"""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None


class HealthStatus(BaseModel):
    """Service health status"""
    status: str = Field(..., description="Overall health status")
    version: str
    uptime_seconds: float
    databases: Dict[str, bool]
    services: Dict[str, bool]
    metrics: Dict[str, Any]