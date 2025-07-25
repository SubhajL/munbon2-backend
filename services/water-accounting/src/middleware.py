"""Middleware for metrics and monitoring"""

from fastapi import FastAPI, Request
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import time
import logging

logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "water_accounting_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status"]
)

REQUEST_DURATION = Histogram(
    "water_accounting_request_duration_seconds",
    "Request duration in seconds",
    ["method", "endpoint"]
)

DELIVERY_COMPLETIONS = Counter(
    "water_accounting_delivery_completions_total",
    "Total number of delivery completions processed"
)

EFFICIENCY_REPORTS = Counter(
    "water_accounting_efficiency_reports_total",
    "Total number of efficiency reports generated"
)

def add_metrics_middleware(app: FastAPI):
    """Add metrics middleware to FastAPI app"""
    
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Record metrics
        duration = time.time() - start_time
        endpoint = request.url.path
        method = request.method
        status = response.status_code
        
        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status=status
        ).inc()
        
        REQUEST_DURATION.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
        
        # Track specific operations
        if endpoint == "/api/v1/delivery/complete" and status == 200:
            DELIVERY_COMPLETIONS.inc()
        elif endpoint == "/api/v1/efficiency/report" and status == 200:
            EFFICIENCY_REPORTS.inc()
        
        return response
    
    @app.get("/metrics")
    async def metrics():
        """Expose Prometheus metrics"""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )