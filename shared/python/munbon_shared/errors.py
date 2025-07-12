"""Custom error classes for Munbon services."""

from typing import Optional, Dict, Any
from datetime import datetime


class BaseError(Exception):
    """Base error class for all custom errors."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for API response."""
        return {
            "error": {
                "message": self.message,
                "code": self.error_code,
                "status_code": self.status_code,
                "details": self.details,
                "timestamp": self.timestamp.isoformat()
            }
        }


class ValidationError(BaseError):
    """Raised when input validation fails."""
    
    def __init__(
        self,
        message: str = "Validation failed",
        errors: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=400,
            error_code="VALIDATION_ERROR",
            details={"validation_errors": errors} if errors else None
        )


class NotFoundError(BaseError):
    """Raised when a resource is not found."""
    
    def __init__(
        self,
        resource: str,
        identifier: Optional[str] = None
    ):
        message = (
            f"{resource} with identifier {identifier} not found"
            if identifier
            else f"{resource} not found"
        )
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND"
        )


class UnauthorizedError(BaseError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(
            message=message,
            status_code=401,
            error_code="UNAUTHORIZED"
        )


class ForbiddenError(BaseError):
    """Raised when user lacks permission."""
    
    def __init__(self, message: str = "Forbidden"):
        super().__init__(
            message=message,
            status_code=403,
            error_code="FORBIDDEN"
        )


class ConflictError(BaseError):
    """Raised when there's a conflict with existing data."""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT"
        )


class RateLimitError(BaseError):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self,
        message: str = "Too many requests",
        retry_after: Optional[int] = None
    ):
        details = {"retry_after": retry_after} if retry_after else None
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details=details
        )


class ServiceUnavailableError(BaseError):
    """Raised when a service is temporarily unavailable."""
    
    def __init__(self, service: str):
        super().__init__(
            message=f"Service {service} is temporarily unavailable",
            status_code=503,
            error_code="SERVICE_UNAVAILABLE"
        )