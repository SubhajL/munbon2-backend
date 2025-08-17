# Munbon Shared Library (Python)

Common utilities, middleware, models, and error handling for Munbon Python microservices built with FastAPI.

## Installation

```bash
pip install munbon-shared

# Or with Poetry
poetry add munbon-shared
```

## Features

### Configuration Management

Environment-based configuration with Pydantic validation:

```python
from munbon_shared import Config, get_config
from pydantic import Field

# Use base configuration
config = get_config()
print(config.service_name)
print(config.database_url)

# Or extend for service-specific config
class ServiceConfig(Config):
    custom_setting: str = Field(
        default="default_value",
        env="CUSTOM_SETTING"
    )
    max_connections: int = Field(
        default=100,
        env="MAX_CONNECTIONS"
    )

config = get_config(ServiceConfig)
```

### Logging

Structured logging with structlog:

```python
from munbon_shared import configure_logging, get_logger

# Configure logging for your service
configure_logging(
    service_name="user-service",
    log_level="INFO",
    json_logs=True  # Use JSON format in production
)

# Get logger instance
logger = get_logger(__name__)

# Log with structured data
logger.info("User created", user_id=user.id, email=user.email)
logger.error("Database error", error=str(e), query=query)
```

### Error Handling

Consistent error classes with automatic API responses:

```python
from munbon_shared import (
    ValidationError,
    NotFoundError,
    UnauthorizedError,
    ConflictError
)

# Raise errors in your handlers
raise NotFoundError("User", user_id)
raise ValidationError("Invalid input", errors={"email": "Invalid format"})
raise ConflictError("Email already exists")

# Errors are automatically converted to proper API responses
```

### FastAPI Middleware

#### Error Handler
```python
from fastapi import FastAPI
from munbon_shared.middleware import ErrorHandlerMiddleware

app = FastAPI()
app.add_middleware(ErrorHandlerMiddleware)
```

#### Request Logger
```python
from munbon_shared.middleware import RequestLoggerMiddleware

app.add_middleware(
    RequestLoggerMiddleware,
    skip_paths=["/health", "/metrics"],
    log_body=False
)
```

#### Request ID
```python
from munbon_shared.middleware import RequestIDMiddleware

app.add_middleware(RequestIDMiddleware)
# Adds X-Request-ID header to all requests/responses
```

#### Rate Limiting
```python
from munbon_shared.middleware import RateLimitMiddleware

app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=60,
    exclude_paths=["/health", "/docs"]
)
```

### Common Models

Pydantic models for consistent data structures:

```python
from munbon_shared import (
    PaginationParams,
    PaginatedResponse,
    ApiResponse,
    HealthCheckResponse,
    User,
    UserRole,
    SensorReading,
    GateControl
)

# Pagination
@app.get("/users")
async def list_users(pagination: PaginationParams = Depends()):
    users = await get_users(
        offset=pagination.offset,
        limit=pagination.limit
    )
    total = await count_users()
    
    return PaginatedResponse.create(
        data=users,
        page=pagination.page,
        limit=pagination.limit,
        total=total
    )

# API Response wrapper
@app.get("/api/user/{user_id}")
async def get_user(user_id: str):
    user = await find_user(user_id)
    return ApiResponse.success_response(
        data=user,
        metadata={"version": "1.0.0"}
    )
```

### Utilities

#### Retry with Exponential Backoff
```python
from munbon_shared import retry_async

@retry_async(max_attempts=3, min_wait=1.0, max_wait=30.0)
async def fetch_from_external_api():
    response = await httpx.get("https://api.example.com/data")
    response.raise_for_status()
    return response.json()
```

#### Circuit Breaker
```python
from munbon_shared import CircuitBreaker

# Create circuit breaker
breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    expected_exception=httpx.HTTPError
)

# Use as context manager
async with breaker:
    response = await external_service.call()

# Or as decorator
@breaker.call
async def call_external_service():
    return await external_service.call()
```

#### Simple Cache
```python
from munbon_shared import SimpleCache

# Create cache instance
cache = SimpleCache(default_ttl=300)  # 5 minutes

# Manual usage
await cache.set("key", "value", ttl=600)
value = await cache.get("key")
await cache.delete("key")

# Decorator usage
@cache.cached(ttl=300)
async def expensive_operation(param: str):
    # This will be cached for 5 minutes
    result = await perform_calculation(param)
    return result
```

## Complete Example

```python
from fastapi import FastAPI, Depends, HTTPException
from contextlib import asynccontextmanager

from munbon_shared import (
    Config,
    get_config,
    configure_logging,
    get_logger,
    ErrorHandlerMiddleware,
    RequestLoggerMiddleware,
    RequestIDMiddleware,
    RateLimitMiddleware,
    NotFoundError,
    PaginationParams,
    PaginatedResponse,
    HealthCheckResponse,
    HealthStatus,
    retry_async
)

# Configuration
config = get_config()

# Logging
configure_logging(
    service_name=config.service_name,
    log_level=config.log_level,
    json_logs=config.is_production
)
logger = get_logger(__name__)

# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Service starting", port=config.port)
    yield
    logger.info("Service shutting down")

# Create app
app = FastAPI(
    title=config.service_name,
    lifespan=lifespan
)

# Add middleware
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    RequestLoggerMiddleware,
    skip_paths=["/health", "/docs", "/openapi.json"]
)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=config.rate_limit_requests
)

# Health check
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    return HealthCheckResponse(
        status=HealthStatus.HEALTHY,
        service=config.service_name,
        version="1.0.0",
        checks={
            "database": {"status": "up"},
            "cache": {"status": "up"}
        }
    )

# Example endpoint with pagination
@app.get("/items")
async def list_items(
    pagination: PaginationParams = Depends()
):
    # Fetch items with retry
    @retry_async(max_attempts=3)
    async def fetch_items():
        # Your database query here
        return await db.fetch_items(
            offset=pagination.offset,
            limit=pagination.limit
        )
    
    items = await fetch_items()
    total = await db.count_items()
    
    return PaginatedResponse.create(
        data=items,
        page=pagination.page,
        limit=pagination.limit,
        total=total
    )

# Example endpoint with error handling
@app.get("/items/{item_id}")
async def get_item(item_id: str):
    item = await db.get_item(item_id)
    if not item:
        raise NotFoundError("Item", item_id)
    return item

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=config.port)
```

## Development

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest

# Format code
poetry run black .

# Lint
poetry run ruff check .

# Type check
poetry run mypy .
```

## Testing

The library includes comprehensive tests. Run them with:

```bash
poetry run pytest --cov=munbon_shared --cov-report=term-missing
```

## Publishing

```bash
# Build the package
poetry build

# Publish to PyPI (or your private registry)
poetry publish
```