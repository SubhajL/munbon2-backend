# Shared Libraries

This directory contains shared code and resources used across multiple microservices.

## Structure

### nodejs
Full-featured Node.js/TypeScript shared library (`@munbon/shared`):
- **logger** - Winston-based structured logging
- **config** - Environment configuration with Joi validation
- **errors** - Custom error classes for consistent error handling
- **middleware** - Express middleware (error handling, request logging, rate limiting, validation)
- **utils** - Utility functions (async handler, retry, circuit breaker, cache)
- **types** - Common TypeScript types and interfaces
- **constants** - System-wide constants

### python
Python shared library (`munbon-shared`) for FastAPI services:
- **config** - Pydantic-based configuration management
- **logging** - Structlog-based structured logging
- **errors** - Custom exception classes
- **middleware** - FastAPI middleware (error handling, request logging, rate limiting)
- **models** - Common Pydantic models
- **utils** - Utility functions (retry, circuit breaker, cache)

### typescript-common
Common TypeScript utilities, interfaces, and middleware used by Node.js services:
- **interfaces** - Shared TypeScript interfaces and types
- **middleware** - Common Express middleware (auth, logging, error handling)
- **utils** - Utility functions (validators, helpers, formatters)
- **constants** - Shared constants and enums

### proto
Protocol Buffer definitions for inter-service communication:
- Service-specific .proto files
- Common message types

### database-schemas
Shared database schemas and migration scripts:
- **postgres** - PostgreSQL/PostGIS schemas
- **timescale** - TimescaleDB specific schemas
- **mongodb** - MongoDB schemas and indexes

## Usage

To use shared libraries in a service:

### Node.js/TypeScript
```typescript
// New comprehensive shared library
import { 
  createLogger, 
  createConfig, 
  errorHandler,
  NotFoundError 
} from '@munbon/shared';

const logger = createLogger('my-service');
const config = createConfig();

// Legacy TypeScript common
import { AuthMiddleware } from '@munbon/typescript-common/middleware';
import { UserInterface } from '@munbon/typescript-common/interfaces';
```

### Python
```python
from munbon_shared import (
    get_logger,
    get_config,
    ErrorHandlerMiddleware,
    NotFoundError
)

logger = get_logger(__name__)
config = get_config()
```

### Protocol Buffers
```bash
protoc --go_out=. --go-grpc_out=. proto/service.proto
```

## Development

When modifying shared libraries:
1. Update version in package.json/pyproject.toml
2. Run tests to ensure compatibility
3. Update all dependent services
4. Document any breaking changes
5. Consider if changes should be propagated to other language libraries

### Publishing

#### Node.js Library
```bash
cd shared/nodejs
npm run build
npm publish
```

#### Python Library
```bash
cd shared/python
poetry build
poetry publish
```

## Best Practices

1. Always use shared error classes for consistency
2. Configure logging early in application startup
3. Use environment-based configuration
4. Apply middleware in the correct order
5. Use retry and circuit breaker for external calls
6. Cache expensive operations appropriately
7. Validate all inputs using validation middleware