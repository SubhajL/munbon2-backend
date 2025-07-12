# Testing Microservices Architecture Guide

## Overview

Testing microservices requires a multi-layered approach, from unit tests to full system integration tests. Each microservice should be testable both in isolation and as part of the larger system.

## Why Docker for Microservices?

### Docker is Recommended (Not Required)

**Benefits:**
1. **Environment Consistency**: Same environment in dev, test, and production
2. **Dependency Isolation**: Each service has its own dependencies
3. **Easy Scaling**: Spin up multiple instances easily
4. **CI/CD Integration**: Seamless pipeline integration
5. **Resource Efficiency**: Lighter than VMs

**Alternative Approaches:**
- **Bare Metal**: Direct installation on servers
- **VMs**: Traditional virtual machines
- **Serverless**: AWS Lambda, Google Cloud Functions
- **PaaS**: Heroku, Google App Engine

## Testing Pyramid for Microservices

```
                    /\
                   /  \
                  / E2E \           (Few)
                 /  Tests \
                /----------\
               / Integration\        (Some)
              /    Tests     \
             /----------------\
            /   Unit Tests     \     (Many)
           /____________________\
```

## 1. Unit Testing (Single Service)

Test individual components within a service in isolation.

### Example: Weather Service Unit Test

```typescript
// weather.service.test.ts
import { WeatherService } from './weather.service';

describe('WeatherService', () => {
  let service: WeatherService;
  let mockDatabase: jest.Mocked<DatabaseService>;
  
  beforeEach(() => {
    mockDatabase = createMockDatabase();
    service = new WeatherService(mockDatabase);
  });

  test('should calculate average temperature', () => {
    const readings = [
      { temperature: 25 },
      { temperature: 27 },
      { temperature: 26 }
    ];
    
    const average = service.calculateAverage(readings);
    expect(average).toBe(26);
  });
});
```

### Running Unit Tests

```bash
# Individual service
cd services/weather-monitoring
npm test

# With coverage
npm run test:coverage

# Watch mode
npm run test:watch
```

## 2. Integration Testing (Service + Dependencies)

Test service with real dependencies (database, cache, message queue).

### Example: API Integration Test

```typescript
// weather.api.integration.test.ts
import request from 'supertest';
import { app } from '../src/app';
import { setupTestDatabase } from './helpers';

describe('Weather API Integration', () => {
  beforeAll(async () => {
    await setupTestDatabase();
  });

  test('GET /api/v1/weather/current', async () => {
    const response = await request(app)
      .get('/api/v1/weather/current')
      .query({ lat: 14.5, lng: 101.3 });
    
    expect(response.status).toBe(200);
    expect(response.body).toMatchObject({
      success: true,
      data: expect.any(Array)
    });
  });
});
```

### Using Test Containers

```typescript
// testcontainers.setup.ts
import { GenericContainer, Network } from 'testcontainers';

export async function setupTestEnvironment() {
  const network = await new Network().start();
  
  // Start PostgreSQL
  const postgres = await new GenericContainer('postgres:14')
    .withEnv('POSTGRES_PASSWORD', 'test')
    .withEnv('POSTGRES_DB', 'weather_test')
    .withExposedPorts(5432)
    .withNetwork(network)
    .start();
  
  // Start Redis
  const redis = await new GenericContainer('redis:7-alpine')
    .withExposedPorts(6379)
    .withNetwork(network)
    .start();
  
  return {
    postgres: {
      host: postgres.getHost(),
      port: postgres.getMappedPort(5432)
    },
    redis: {
      host: redis.getHost(),
      port: redis.getMappedPort(6379)
    },
    cleanup: async () => {
      await postgres.stop();
      await redis.stop();
      await network.stop();
    }
  };
}
```

## 3. Contract Testing (Inter-Service Communication)

Ensure services can communicate correctly.

### Example: Pact Contract Test

```typescript
// weather.consumer.pact.test.ts
import { Pact } from '@pact-foundation/pact';
import { getWeatherFromMoistureService } from './client';

describe('Weather Consumer', () => {
  const provider = new Pact({
    consumer: 'WeatherService',
    provider: 'MoistureService',
  });

  beforeAll(() => provider.setup());
  afterAll(() => provider.finalize());

  test('should receive moisture data', async () => {
    await provider.addInteraction({
      state: 'moisture data exists',
      uponReceiving: 'a request for moisture readings',
      withRequest: {
        method: 'GET',
        path: '/api/v1/moisture/current',
      },
      willRespondWith: {
        status: 200,
        body: {
          moistureLevel: 65.5,
          timestamp: '2024-01-15T10:00:00Z'
        }
      }
    });

    const moisture = await getWeatherFromMoistureService();
    expect(moisture.moistureLevel).toBe(65.5);
  });
});
```

## 4. End-to-End Testing (Full System)

Test complete user journeys across multiple services.

### Example: Full Irrigation Flow

```typescript
// irrigation-flow.e2e.test.ts
describe('Irrigation Decision Flow', () => {
  test('should trigger irrigation based on weather', async () => {
    // 1. Simulate sensor data
    await publishSensorData({
      temperature: 35,
      humidity: 30,
      soilMoisture: 40
    });
    
    // 2. Check weather service processed data
    const weather = await getWeatherData();
    expect(weather.temperature).toBe(35);
    
    // 3. Check irrigation recommendation
    const recommendation = await getIrrigationRecommendation();
    expect(recommendation.action).toBe('irrigate');
    
    // 4. Verify notification sent
    const notifications = await getNotifications();
    expect(notifications).toContainEqual(
      expect.objectContaining({
        type: 'irrigation_needed'
      })
    );
  });
});
```

## 5. Load Testing

Test system performance under load.

### Using k6

```javascript
// load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 100 },   // Ramp up
    { duration: '5m', target: 1000 },  // Stay at 1000 users
    { duration: '2m', target: 0 },     // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% of requests under 500ms
    http_req_failed: ['rate<0.1'],    // Error rate under 10%
  },
};

export default function() {
  // Test weather API
  let weatherRes = http.get('http://api-gateway/api/weather/current');
  check(weatherRes, {
    'weather status 200': (r) => r.status === 200,
  });
  
  // Test moisture API
  let moistureRes = http.get('http://api-gateway/api/moisture/current');
  check(moistureRes, {
    'moisture status 200': (r) => r.status === 200,
  });
  
  sleep(1);
}
```

## Testing in Docker

### 1. Single Service Test

```bash
# Build and test single service
docker build -t weather-service-test --target test .
docker run --rm weather-service-test npm test
```

### 2. Multi-Service Test Stack

```yaml
# docker-compose.test.yml
version: '3.8'

services:
  api-gateway:
    image: kong:3.0
    environment:
      - KONG_DATABASE=off
      - KONG_DECLARATIVE_CONFIG=/kong/kong.yml
    volumes:
      - ./test/kong.yml:/kong/kong.yml
    ports:
      - "8000:8000"
    
  weather-service:
    build: ./services/weather-monitoring
    environment:
      - NODE_ENV=test
      - DB_HOST=test-db
    depends_on:
      - test-db
      - test-redis
  
  moisture-service:
    build: ./services/moisture-monitoring
    environment:
      - NODE_ENV=test
      - DB_HOST=test-db
    depends_on:
      - test-db
      - test-redis
  
  test-db:
    image: postgres:14
    environment:
      - POSTGRES_PASSWORD=test
      - POSTGRES_DB=test_db
  
  test-redis:
    image: redis:7-alpine
```

### 3. Running Test Suite

```bash
# Start test environment
docker-compose -f docker-compose.test.yml up -d

# Run integration tests
npm run test:integration

# Run E2E tests
npm run test:e2e

# Clean up
docker-compose -f docker-compose.test.yml down -v
```

## CI/CD Pipeline Testing

### GitHub Actions Example

```yaml
name: Microservices Test Pipeline

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: [weather-monitoring, moisture-monitoring, water-level-monitoring]
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Run unit tests
        run: |
          cd services/${{ matrix.service }}
          npm ci
          npm test

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v3
      - name: Run integration tests
        run: |
          docker-compose -f docker-compose.test.yml up -d
          npm run test:integration
          docker-compose -f docker-compose.test.yml down

  e2e-tests:
    runs-on: ubuntu-latest
    needs: integration-tests
    steps:
      - uses: actions/checkout@v3
      - name: Deploy test stack
        run: |
          docker-compose -f docker-compose.yml up -d
          ./scripts/wait-for-services.sh
      - name: Run E2E tests
        run: npm run test:e2e
      - name: Cleanup
        if: always()
        run: docker-compose down -v
```

## Debugging Microservices

### 1. Local Debugging

```bash
# Debug single service
cd services/weather-monitoring
DEBUG=* npm run dev

# Remote debugging
node --inspect=0.0.0.0:9229 dist/index.js
```

### 2. Distributed Tracing

```yaml
# Add Jaeger for tracing
services:
  jaeger:
    image: jaegertracing/all-in-one
    ports:
      - "16686:16686"  # UI
      - "6831:6831/udp" # Traces
```

### 3. Log Aggregation

```yaml
# Add Loki for logs
services:
  loki:
    image: grafana/loki
    ports:
      - "3100:3100"
  
  promtail:
    image: grafana/promtail
    volumes:
      - /var/log:/var/log
      - ./promtail-config.yml:/etc/promtail/config.yml
```

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Test Data**: Use factories/fixtures for consistent test data
3. **Mock External Services**: Use WireMock or similar
4. **Timeouts**: Set appropriate timeouts for async operations
5. **Cleanup**: Always clean up test data and resources
6. **Parallel Testing**: Run tests in parallel when possible
7. **Test Environments**: Maintain separate test environments
8. **Monitoring**: Monitor test execution and results

## Common Issues and Solutions

### 1. Port Conflicts
```bash
# Use dynamic ports in tests
const server = app.listen(0); // Random available port
const port = server.address().port;
```

### 2. Database State
```typescript
// Reset database between tests
beforeEach(async () => {
  await db.query('TRUNCATE TABLE weather_readings CASCADE');
});
```

### 3. Timing Issues
```typescript
// Use proper waits
await waitFor(() => {
  expect(mockFn).toHaveBeenCalled();
}, { timeout: 5000 });
```

### 4. Service Discovery
```typescript
// Use environment variables for service URLs
const WEATHER_SERVICE = process.env.WEATHER_SERVICE_URL || 'http://localhost:3055';
```

## Testing Checklist

- [ ] Unit tests for business logic
- [ ] Integration tests for APIs
- [ ] Contract tests for service communication
- [ ] E2E tests for critical user journeys
- [ ] Load tests for performance requirements
- [ ] Security tests for authentication/authorization
- [ ] Chaos tests for resilience
- [ ] Smoke tests for deployments