# Weather Monitoring Service - Testing Guide

## Testing Levels

### 1. Unit Testing (Individual Components)

```bash
# Run unit tests
npm test

# Run with coverage
npm run test:coverage

# Watch mode during development
npm run test:watch
```

Example unit test:
```typescript
// test/services/analytics.service.test.ts
describe('AnalyticsService', () => {
  it('should calculate evapotranspiration correctly', async () => {
    const mockData = {
      temperature: 25,
      humidity: 65,
      windSpeed: 10,
      solarRadiation: 200
    };
    
    const result = await analyticsService.calculateEvapotranspiration(
      { lat: 14.5, lng: 101.3 },
      new Date(),
      1.2 // crop coefficient
    );
    
    expect(result.et0).toBeCloseTo(4.5, 1);
    expect(result.etc).toBeCloseTo(5.4, 1);
  });
});
```

### 2. Integration Testing (Service + Dependencies)

```bash
# Run integration tests
npm run test:integration

# Using docker-compose for test environment
docker-compose -f docker-compose.test.yml up -d
npm run test:integration
docker-compose -f docker-compose.test.yml down
```

Example integration test:
```typescript
// test/integration/weather.api.test.ts
describe('Weather API Integration', () => {
  beforeAll(async () => {
    // Start test containers
    await dockerCompose.up();
    await waitForServices();
  });

  it('should get current weather from database', async () => {
    // Insert test data
    await insertTestWeatherData();
    
    const response = await request(app)
      .get('/api/v1/weather/current')
      .query({ lat: 14.5, lng: 101.3 });
    
    expect(response.status).toBe(200);
    expect(response.body.data).toHaveLength(1);
    expect(response.body.data[0].temperature).toBe(25.5);
  });
});
```

### 3. Contract Testing (API Contracts)

```bash
# Using Pact for contract testing
npm run test:contracts
```

Example contract test:
```typescript
// test/contracts/weather.consumer.pact.ts
describe('Weather Service Consumer', () => {
  it('should receive weather data', async () => {
    await provider.addInteraction({
      state: 'weather data exists',
      uponReceiving: 'a request for current weather',
      withRequest: {
        method: 'GET',
        path: '/api/v1/weather/current',
        query: { lat: '14.5', lng: '101.3' }
      },
      willRespondWith: {
        status: 200,
        body: {
          success: true,
          data: Matchers.eachLike({
            stationId: Matchers.string(),
            temperature: Matchers.decimal(),
            humidity: Matchers.decimal()
          })
        }
      }
    });
  });
});
```

### 4. End-to-End Testing (Multiple Services)

```bash
# Run E2E tests against all services
npm run test:e2e
```

Example E2E test:
```typescript
// test/e2e/irrigation-flow.test.ts
describe('Irrigation Recommendation Flow', () => {
  it('should get recommendation based on weather data', async () => {
    // 1. Sensor sends data via MQTT
    await mqttClient.publish('sensor/weather/CUSTOM001/data', {
      temperature: 35,
      humidity: 45,
      timestamp: new Date()
    });
    
    // 2. Wait for processing
    await sleep(2000);
    
    // 3. Request irrigation recommendation
    const response = await axios.get('http://api-gateway/api/weather/irrigation/recommendation', {
      params: {
        lat: 14.5,
        lng: 101.3,
        cropType: 'rice',
        growthStage: 'vegetative'
      }
    });
    
    expect(response.data.recommendation).toBe('irrigate');
    expect(response.data.suggestedAmount).toBeGreaterThan(0);
  });
});
```

## Testing Individual Microservices

### 1. Isolated Testing
```bash
# Start only the service under test with mocked dependencies
docker run -d --name test-weather \
  -e MOCK_MODE=true \
  -p 3055:3055 \
  weather-monitoring

# Run tests against it
npm run test:api
```

### 2. Component Testing with Test Containers
```typescript
// Using testcontainers-node
import { GenericContainer } from 'testcontainers';

describe('Weather Service Component Test', () => {
  let weatherContainer;
  let redisContainer;
  
  beforeAll(async () => {
    // Start Redis
    redisContainer = await new GenericContainer('redis:7-alpine')
      .withExposedPorts(6379)
      .start();
    
    // Start Weather Service
    weatherContainer = await new GenericContainer('weather-monitoring')
      .withEnv('REDIS_HOST', redisContainer.getHost())
      .withEnv('REDIS_PORT', redisContainer.getMappedPort(6379))
      .withExposedPorts(3055)
      .start();
  });
});
```

## Testing Service Combinations

### 1. Docker Compose Test Stack
```yaml
# docker-compose.test.yml
version: '3.8'
services:
  weather-monitoring:
    build: ../weather-monitoring
    environment:
      - NODE_ENV=test
      - LOG_LEVEL=error
    depends_on:
      - test-db
      - test-redis
  
  moisture-monitoring:
    build: ../moisture-monitoring
    environment:
      - NODE_ENV=test
    depends_on:
      - test-db
      - test-redis
  
  test-db:
    image: postgres:14-alpine
    environment:
      - POSTGRES_DB=test_db
      - POSTGRES_PASSWORD=test
  
  test-redis:
    image: redis:7-alpine
```

### 2. Service Mesh Testing
```bash
# Using Istio for service mesh testing
kubectl apply -f test/k8s/test-namespace.yaml
kubectl apply -f test/k8s/test-services.yaml

# Run traffic testing
kubectl run -it test-client --image=curlimages/curl --rm -- sh
# Inside pod:
curl http://weather-monitoring:3055/health
curl http://moisture-monitoring:3044/health
```

### 3. Load Testing
```bash
# Using k6 for load testing
k6 run test/load/weather-service.js
```

```javascript
// test/load/weather-service.js
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 100 },
    { duration: '5m', target: 1000 },
    { duration: '2m', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% of requests under 500ms
  },
};

export default function() {
  let response = http.get('http://localhost:3055/api/v1/weather/current?lat=14.5&lng=101.3');
  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
}
```

## Testing Tools

### Local Development
- **Jest**: Unit and integration tests
- **Supertest**: API testing
- **Testcontainers**: Docker-based integration tests

### CI/CD Pipeline
```yaml
# .github/workflows/test.yml
name: Test Microservices
on: [push, pull_request]

jobs:
  test-weather-service:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run unit tests
        run: |
          cd services/weather-monitoring
          npm install
          npm test
      
      - name: Run integration tests
        run: |
          docker-compose -f docker-compose.test.yml up -d
          npm run test:integration
          docker-compose down
```

### Service Communication Testing
```bash
# Test MQTT communication
mosquitto_sub -h localhost -t weather/# &
mosquitto_pub -h localhost -t weather/test -m "test message"

# Test WebSocket connection
wscat -c ws://localhost:3055
> {"event": "subscribe:weather", "data": {"location": {"lat": 14.5, "lng": 101.3}}}

# Test REST API
curl -X GET http://localhost:3055/api/v1/weather/current

# Test service-to-service communication
curl -X POST http://localhost:3055/test/trigger-alert
```

## Debugging Microservices

### 1. Individual Service Debugging
```bash
# Run with debug logging
DEBUG=* npm start

# Attach debugger
node --inspect=0.0.0.0:9229 dist/index.js
```

### 2. Distributed Tracing
```yaml
# Add OpenTelemetry/Jaeger
services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"
      - "14268:14268"
```

### 3. Service Logs Aggregation
```bash
# View logs from all services
docker-compose logs -f

# Filter specific service
docker-compose logs -f weather-monitoring | grep ERROR

# Using Loki for log aggregation
docker run -d -p 3100:3100 grafana/loki
```

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Mock External Services**: Use WireMock or similar for external APIs
3. **Test Data Management**: Use fixtures and clean up after tests
4. **Environment Parity**: Test environment should match production
5. **Continuous Testing**: Run tests on every commit
6. **Performance Baselines**: Establish and monitor performance metrics

## Common Test Scenarios

### 1. Service Health Check
```bash
# All services should respond to health checks
for port in 3055 3044 3046; do
  curl -f http://localhost:$port/health || echo "Service on port $port is down"
done
```

### 2. Database Connection Test
```typescript
it('should connect to both databases', async () => {
  const pgHealth = await databaseService.checkPostgresHealth();
  const tsHealth = await databaseService.checkTimescaleHealth();
  
  expect(pgHealth).toBe(true);
  expect(tsHealth).toBe(true);
});
```

### 3. Message Queue Test
```typescript
it('should process messages from queue', async () => {
  const testMessage = { temperature: 25, humidity: 65 };
  
  await mqttClient.publish('sensor/weather/TEST001/data', testMessage);
  
  // Wait for processing
  await waitFor(() => {
    const cached = cacheService.get('weather:current:TEST001');
    expect(cached).toBeDefined();
  });
});
```