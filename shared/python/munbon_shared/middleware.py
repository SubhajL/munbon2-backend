"""FastAPI middleware for Munbon services."""

import time
import uuid
from typing import Callable, Optional, Dict, Any
from datetime import datetime

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from munbon_shared.errors import BaseError, RateLimitError
from munbon_shared.logging import get_logger

logger = get_logger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware for handling errors consistently."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except BaseError as e:
            logger.error(
                "Application error",
                error_type=type(e).__name__,
                error_message=str(e),
                status_code=e.status_code,
                path=request.url.path,
                method=request.method
            )
            return JSONResponse(
                status_code=e.status_code,
                content=e.to_dict()
            )
        except Exception as e:
            logger.exception(
                "Unhandled error",
                error_type=type(e).__name__,
                error_message=str(e),
                path=request.url.path,
                method=request.method
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": {
                        "message": "Internal server error",
                        "code": "INTERNAL_ERROR",
                        "status_code": 500,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests."""
    
    def __init__(
        self,
        app: ASGIApp,
        skip_paths: Optional[list[str]] = None,
        log_body: bool = False
    ):
        super().__init__(app)
        self.skip_paths = skip_paths or ["/health", "/ready", "/metrics", "/docs"]
        self.log_body = log_body
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip logging for certain paths
        if any(request.url.path.startswith(path) for path in self.skip_paths):
            return await call_next(request)
        
        # Start timing
        start_time = time.time()
        
        # Get request ID
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        
        # Log request
        log_data = {
            "event": "request_started",
            "method": request.method,
            "path": request.url.path,
            "query": str(request.url.query),
            "request_id": request_id,
            "client_host": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent")
        }
        
        if self.log_body and request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                await request.receive()  # Reset body stream
                log_data["body_size"] = len(body)
            except Exception:
                pass
        
        logger.info("HTTP Request", **log_data)
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            "HTTP Response",
            event="request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
            request_id=request_id
        )
        
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware for adding request ID to requests and responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate request ID
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        
        # Store in request state for access in handlers
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware."""
    
    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        exclude_paths: Optional[list[str]] = None
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.exclude_paths = exclude_paths or ["/health", "/ready", "/metrics"]
        self.requests: Dict[str, list[float]] = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Get client identifier
        client_id = request.client.host if request.client else "unknown"
        
        # Get current time
        now = time.time()
        minute_ago = now - 60
        
        # Clean old requests
        if client_id in self.requests:
            self.requests[client_id] = [
                req_time for req_time in self.requests[client_id]
                if req_time > minute_ago
            ]
        else:
            self.requests[client_id] = []
        
        # Check rate limit
        if len(self.requests[client_id]) >= self.requests_per_minute:
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                path=request.url.path,
                requests_count=len(self.requests[client_id])
            )
            raise RateLimitError(
                f"Rate limit exceeded: {self.requests_per_minute} requests per minute",
                retry_after=60
            )
        
        # Record request
        self.requests[client_id].append(now)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            self.requests_per_minute - len(self.requests[client_id])
        )
        response.headers["X-RateLimit-Reset"] = str(int(minute_ago + 60))
        
        return response


# Convenience functions for adding middleware
def error_handler(app: ASGIApp) -> ErrorHandlerMiddleware:
    """Create error handler middleware."""
    return ErrorHandlerMiddleware(app)


def request_logger(
    app: ASGIApp,
    skip_paths: Optional[list[str]] = None,
    log_body: bool = False
) -> RequestLoggerMiddleware:
    """Create request logger middleware."""
    return RequestLoggerMiddleware(app, skip_paths, log_body)


def request_id_middleware(app: ASGIApp) -> RequestIDMiddleware:
    """Create request ID middleware."""
    return RequestIDMiddleware(app)


def rate_limit_middleware(
    app: ASGIApp,
    requests_per_minute: int = 60,
    exclude_paths: Optional[list[str]] = None
) -> RateLimitMiddleware:
    """Create rate limit middleware."""
    return RateLimitMiddleware(app, requests_per_minute, exclude_paths)