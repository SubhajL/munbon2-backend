# Claude Instance 5: External Data API

## Scope of Work
This instance handles all external-facing APIs, data aggregation from multiple services, and serves as the primary interface for client applications.

## Assigned Components

### 1. **Unified API Service**
- **Path**: `/services/sensor-data/src/unified-api.js`
- **Port**: 3000 (Local), AWS Lambda (Production)
- **Responsibilities**:
  - Aggregate data from all internal services
  - Provide RESTful API endpoints
  - Handle API authentication
  - Implement rate limiting
  - Response caching
  - Data transformation for clients

### 2. **API Gateway Configuration**
- **Path**: `/infrastructure/kong` or `/api-gateway`
- **Port**: 8000 (Proxy), 8001 (Admin)
- **Responsibilities**:
  - Route management
  - Load balancing
  - Authentication gateway
  - Rate limiting policies
  - API versioning
  - Request/response transformation

### 3. **GraphQL API** (Future)
- **Path**: `/services/api-gateway/graphql`
- **Port**: 4000
- **Responsibilities**:
  - GraphQL schema definition
  - Resolver implementation
  - Subscription support
  - Schema stitching

## Environment Setup

```bash
# Unified API Service
cat > services/sensor-data/.env.external-api << EOF
# External API Configuration
SERVICE_NAME=external-api
API_PORT=3000
NODE_ENV=development

# API Authentication
API_KEY_HEADER=x-api-key
ENABLE_API_KEY_AUTH=true
JWT_PUBLIC_KEY_PATH=/keys/public.pem

# Rate Limiting
RATE_LIMIT_WINDOW_MS=900000  # 15 minutes
RATE_LIMIT_MAX_FREE=100
RATE_LIMIT_MAX_BASIC=1000
RATE_LIMIT_MAX_PREMIUM=10000

# Caching
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=7
CACHE_TTL_DEFAULT=300  # 5 minutes
CACHE_TTL_STATIC=3600  # 1 hour

# Internal Service URLs
AUTH_SERVICE=http://localhost:3001
SENSOR_SERVICE=http://localhost:3003
GIS_SERVICE=http://localhost:3007
WATER_LEVEL_SERVICE=http://localhost:3008
MOISTURE_SERVICE=http://localhost:3005
WEATHER_SERVICE=http://localhost:3006
ROS_SERVICE=http://localhost:3047
RID_MS_SERVICE=http://localhost:3009

# AWS Configuration (for Lambda)
AWS_REGION=ap-southeast-1
API_GATEWAY_URL=https://api.munbon.go.th

# Response Configuration
ENABLE_RESPONSE_COMPRESSION=true
MAX_PAGE_SIZE=100
DEFAULT_PAGE_SIZE=20

# CORS Configuration
CORS_ORIGINS=https://app.munbon.go.th,http://localhost:3000
CORS_METHODS=GET,POST,PUT,DELETE,OPTIONS
EOF
```

## API Structure

### Public Endpoints (No Auth)
```
GET /health
GET /api/v1/status
GET /api/v1/docs
GET /api/v1/schemas/{schemaName}
```

### Authenticated Endpoints

#### Sensor Data Aggregation
```
# Water Level
GET /api/v1/sensors/water-level/latest
GET /api/v1/sensors/water-level/timeseries?start={}&end={}
GET /api/v1/sensors/water-level/statistics?period={daily|weekly|monthly}

# Moisture
GET /api/v1/sensors/moisture/latest
GET /api/v1/sensors/moisture/field/{fieldId}
GET /api/v1/sensors/moisture/irrigation-status

# Weather
GET /api/v1/sensors/weather/current
GET /api/v1/sensors/weather/forecast?days={}
GET /api/v1/sensors/weather/history?date={}
```

#### GIS Data
```
GET /api/v1/gis/parcels?zone={}&page={}&limit={}
GET /api/v1/gis/parcels/{parcelId}
GET /api/v1/gis/zones
GET /api/v1/gis/zones/{zoneId}/summary
GET /api/v1/gis/map/tiles/{z}/{x}/{y}
```

#### Analytics & Calculations
```
GET /api/v1/analytics/water-demand?zone={}&date={}
GET /api/v1/analytics/irrigation-schedule?zone={}
GET /api/v1/analytics/crop-status?zone={}
POST /api/v1/analytics/calculate-eto
```

#### Dashboard Endpoints
```
GET /api/v1/dashboard/summary
GET /api/v1/dashboard/alerts
GET /api/v1/dashboard/sensors/status
GET /api/v1/dashboard/water-distribution
```

## Response Formats

### Standard Success Response
```json
{
  "success": true,
  "data": {
    // Response data
  },
  "meta": {
    "timestamp": "2024-07-08T10:30:00Z",
    "version": "1.0.0",
    "requestId": "req_abc123",
    "cached": false
  },
  "pagination": {
    "page": 1,
    "perPage": 20,
    "total": 150,
    "totalPages": 8
  }
}
```

### Error Response
```json
{
  "success": false,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested resource was not found",
    "details": {
      "resource": "parcel",
      "id": "P12345"
    },
    "timestamp": "2024-07-08T10:30:00Z"
  },
  "meta": {
    "requestId": "req_abc123",
    "documentation": "https://api.munbon.go.th/docs#errors"
  }
}
```

## Data Aggregation Logic

```javascript
// Aggregate sensor data from multiple services
async function getDashboardSummary(zoneId, date) {
  // Parallel fetch from all services
  const [waterLevel, moisture, weather, gis] = await Promise.all([
    fetchWaterLevelSummary(zoneId, date),
    fetchMoistureSummary(zoneId, date),
    fetchWeatherSummary(zoneId, date),
    fetchGISSummary(zoneId)
  ]);
  
  // Calculate derived metrics
  const waterDemand = calculateWaterDemand(moisture, weather, gis);
  const irrigationStatus = determineIrrigationStatus(waterLevel, waterDemand);
  
  return {
    zone: gis,
    sensors: {
      waterLevel: waterLevel,
      moisture: moisture,
      weather: weather
    },
    calculations: {
      waterDemand: waterDemand,
      irrigationNeeded: irrigationStatus.needed,
      recommendedSchedule: irrigationStatus.schedule
    },
    alerts: combineAlerts([waterLevel.alerts, moisture.alerts, weather.alerts])
  };
}
```

## Caching Strategy

```javascript
// Redis cache keys and TTL
const cacheConfig = {
  'sensor:water-level:latest': 60,      // 1 minute
  'sensor:moisture:latest': 300,        // 5 minutes
  'sensor:weather:current': 300,        // 5 minutes
  'gis:zones:list': 3600,              // 1 hour
  'gis:parcels:{id}': 1800,            // 30 minutes
  'analytics:water-demand:{zone}': 900, // 15 minutes
  'dashboard:summary:{zone}': 300      // 5 minutes
};

// Cache middleware
async function cacheMiddleware(req, res, next) {
  const cacheKey = generateCacheKey(req);
  const cached = await redis.get(cacheKey);
  
  if (cached) {
    return res.json({
      ...JSON.parse(cached),
      meta: { ...meta, cached: true }
    });
  }
  
  // Store original res.json
  const originalJson = res.json.bind(res);
  
  // Override res.json to cache response
  res.json = (data) => {
    redis.setex(cacheKey, getTTL(req.path), JSON.stringify(data));
    originalJson(data);
  };
  
  next();
}
```

## Rate Limiting Tiers

```javascript
const rateLimitTiers = {
  free: {
    windowMs: 15 * 60 * 1000,  // 15 minutes
    max: 100,
    message: 'Free tier limit exceeded. Upgrade to Basic for more requests.'
  },
  basic: {
    windowMs: 15 * 60 * 1000,
    max: 1000,
    message: 'Basic tier limit exceeded. Upgrade to Premium.'
  },
  premium: {
    windowMs: 15 * 60 * 1000,
    max: 10000,
    message: 'Premium tier limit exceeded. Contact support for Enterprise.'
  },
  enterprise: {
    windowMs: 15 * 60 * 1000,
    max: Infinity
  }
};
```

## API Gateway (Kong) Configuration

```yaml
services:
  - name: external-api
    url: http://localhost:3000
    routes:
      - name: api-v1-public
        paths:
          - /api/v1/health
          - /api/v1/status
        methods: [GET]
      
      - name: api-v1-authenticated
        paths:
          - /api/v1
        methods: [GET, POST, PUT, DELETE]
        plugins:
          - name: key-auth
            config:
              key_names: [x-api-key]
          - name: rate-limiting
            config:
              policy: local
              minute: 100
          - name: cors
            config:
              origins: ['*']
              methods: [GET, POST, PUT, DELETE, OPTIONS]
          - name: request-transformer
            config:
              add:
                headers:
                  X-Request-ID: "$(uuid)"
```

## Current Status
- ✅ Basic unified API structure
- ✅ API key authentication
- ✅ AWS Lambda deployment ready
- ⚠️ Data aggregation: Partial
- ⚠️ Caching: Basic implementation
- ❌ GraphQL API: Not started
- ❌ WebSocket support: Not implemented
- ❌ API documentation portal: Not created

## Priority Tasks
1. Complete data aggregation endpoints
2. Implement comprehensive caching
3. Set up Kong API Gateway
4. Build API documentation portal
5. Add WebSocket for real-time data
6. Implement GraphQL API
7. Add request validation middleware
8. Build API key management system

## Testing Commands

```bash
# Test public endpoint
curl http://localhost:3000/health

# Test with API key
curl -H "x-api-key: test-key-123" \
  http://localhost:3000/api/v1/dashboard/summary

# Test pagination
curl -H "x-api-key: test-key-123" \
  "http://localhost:3000/api/v1/gis/parcels?page=2&limit=50"

# Test data aggregation
curl -H "x-api-key: test-key-123" \
  "http://localhost:3000/api/v1/sensors/all/latest?zone=Z1"

# Test caching (run twice, check cached flag)
curl -H "x-api-key: test-key-123" \
  http://localhost:3000/api/v1/gis/zones
```

## API Documentation

```javascript
// Auto-generate OpenAPI docs
app.get('/api/v1/docs', (req, res) => {
  res.json(generateOpenAPISpec());
});

// Serve Swagger UI
app.use('/api/docs', swaggerUi.serve, swaggerUi.setup(openapiSpec));
```

## Performance Optimizations
- Use DataLoader for batching internal API calls
- Implement response compression
- Add ETags for client-side caching
- Use database connection pooling
- Implement query result caching
- Add CDN for static resources
- Use HTTP/2 for multiplexing

## Notes for Development
- Always version APIs properly (/v1/, /v2/)
- Implement field filtering (?fields=id,name)
- Add sorting support (?sort=-createdAt)
- Use consistent error codes
- Log all API requests for analytics
- Monitor response times
- Implement circuit breakers
- Add health checks for dependencies