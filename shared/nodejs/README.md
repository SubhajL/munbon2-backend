# Munbon Shared Library (Node.js/TypeScript)

Common utilities, middleware, types, and constants shared across Munbon microservices built with Node.js/TypeScript.

## Installation

```bash
npm install @munbon/shared
```

## Features

### Logger
Structured logging with Winston, supporting different log levels and formats.

```typescript
import { createLogger } from '@munbon/shared';

const logger = createLogger('my-service');
logger.info('Service started', { port: 3000 });
logger.error('Database connection failed', { error: err.message });
```

### Configuration
Environment variable validation and configuration management using Joi.

```typescript
import { createConfig } from '@munbon/shared';
import joi from 'joi';

// Extend base configuration
const schema = joi.object({
  DATABASE_URL: joi.string().uri().required(),
  CACHE_SIZE: joi.number().default(1000)
});

const config = createConfig(schema);
// config includes both base config and your custom fields
```

### Error Handling
Consistent error classes and middleware for Express applications.

```typescript
import { 
  BaseError, 
  ValidationError, 
  NotFoundError,
  errorHandler 
} from '@munbon/shared';

// Throw errors
throw new NotFoundError('User', userId);
throw new ValidationError('Invalid input', { email: 'Invalid email format' });

// Use error handler middleware
app.use(errorHandler);
```

### Middleware

#### Request Logger
```typescript
import { requestLogger } from '@munbon/shared';

app.use(requestLogger({
  skipPaths: ['/health', '/metrics'],
  logBody: true
}));
```

#### Rate Limiter
```typescript
import { createRateLimiter } from '@munbon/shared';

app.use(createRateLimiter({
  windowMs: 15 * 60 * 1000, // 15 minutes
  maxRequests: 100
}));
```

#### Request ID
```typescript
import { requestId } from '@munbon/shared';

app.use(requestId());
// Adds X-Request-ID header to requests and responses
```

#### Validation
```typescript
import { validate } from '@munbon/shared';
import joi from 'joi';

const createUserSchema = joi.object({
  email: joi.string().email().required(),
  name: joi.string().min(3).required()
});

router.post('/users', 
  validate(createUserSchema),
  async (req, res) => {
    // req.body is validated and typed
  }
);
```

### Utilities

#### Async Handler
Wraps async route handlers to properly catch errors.

```typescript
import { asyncHandler } from '@munbon/shared';

router.get('/users/:id', asyncHandler(async (req, res) => {
  const user = await userService.findById(req.params.id);
  res.json(user);
}));
```

#### Retry Mechanism
```typescript
import { retry } from '@munbon/shared';

const result = await retry(
  () => fetchDataFromExternalAPI(),
  {
    maxAttempts: 3,
    delay: 1000,
    backoffMultiplier: 2
  }
);
```

#### Circuit Breaker
```typescript
import { CircuitBreaker } from '@munbon/shared';

const breaker = new CircuitBreaker(
  async () => externalServiceCall(),
  {
    failureThreshold: 50, // 50% failure rate opens circuit
    resetTimeout: 60000   // Try again after 1 minute
  }
);

try {
  const result = await breaker.execute();
} catch (error) {
  // Handle error or circuit open
}
```

#### Simple Cache
```typescript
import { SimpleCache, cacheable } from '@munbon/shared';

// Manual cache usage
const cache = new SimpleCache<string>(60000); // 1 minute TTL
cache.set('key', 'value');
const value = cache.get('key');

// Decorator usage
class UserService {
  @cacheable(300000) // 5 minutes
  async findById(id: string): Promise<User> {
    return await db.users.findById(id);
  }
}
```

### Types
Common TypeScript types for consistent data structures.

```typescript
import { 
  User,
  UserRole,
  SensorReading,
  GateControl,
  Notification,
  ApiResponse,
  PaginatedResponse 
} from '@munbon/shared';
```

### Constants
System-wide constants for consistency.

```typescript
import { 
  SYSTEM_CONSTANTS,
  SENSOR_TYPES,
  UNITS,
  PERMISSIONS,
  PATTERNS 
} from '@munbon/shared';

// Use in your service
const maxFileSize = SYSTEM_CONSTANTS.MAX_FILE_SIZE;
const waterLevelUnit = UNITS.WATER_LEVEL;
```

## Complete Example

```typescript
import express from 'express';
import {
  createLogger,
  createConfig,
  errorHandler,
  requestLogger,
  requestId,
  createRateLimiter,
  asyncHandler,
  NotFoundError,
  validate,
  ApiResponse
} from '@munbon/shared';
import joi from 'joi';

// Configuration
const schema = joi.object({
  DATABASE_URL: joi.string().uri().required()
});
const config = createConfig(schema);

// Logger
const logger = createLogger('user-service');

// Express app
const app = express();

// Middleware
app.use(express.json());
app.use(requestId());
app.use(requestLogger());
app.use(createRateLimiter());

// Route with validation
const getUserSchema = joi.object({
  id: joi.string().uuid().required()
});

app.get('/users/:id', 
  validate(getUserSchema, { target: 'params' }),
  asyncHandler(async (req, res) => {
    const user = await userService.findById(req.params.id);
    
    if (!user) {
      throw new NotFoundError('User', req.params.id);
    }
    
    const response: ApiResponse<User> = {
      success: true,
      data: user,
      metadata: {
        timestamp: new Date(),
        version: '1.0.0',
        requestId: req.headers['x-request-id'] as string
      }
    };
    
    res.json(response);
  })
);

// Error handler (must be last)
app.use(errorHandler);

// Start server
app.listen(config.PORT, () => {
  logger.info('Server started', { port: config.PORT });
});
```

## Development

```bash
# Install dependencies
npm install

# Build
npm run build

# Run tests
npm test

# Lint
npm run lint
```

## Publishing

The library is configured to publish to a local Verdaccio registry by default. Update the `publishConfig` in package.json for your registry.

```bash
# Build and publish
npm run prepublishOnly
npm publish
```