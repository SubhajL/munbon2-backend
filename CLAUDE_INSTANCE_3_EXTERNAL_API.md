# Claude Instance 3: External Data API

## Scope of Work
This instance handles all external-facing APIs, data aggregation, and public endpoints for client applications.

## Assigned Services

### 1. **Unified API Service** (Primary)
- **Path**: `/services/sensor-data/src/unified-api.js`
- **Port**: 3000 (Local), AWS Lambda (Production)
- **Responsibilities**:
  - Aggregate data from multiple sources
  - Public REST API endpoints
  - API key authentication
  - Rate limiting
  - Response caching

### 2. **API Gateway Configuration**
- **Path**: `/infrastructure/kong` or `/api-gateway`
- **Port**: 8000 (Proxy), 8001 (Admin)
- **Responsibilities**:
  - Route management
  - Authentication
  - Rate limiting
  - API versioning
  - Monitoring

### 3. **External Integrations**
- **Path**: Various service integrations
- **Responsibilities**:
  - Thai Meteorological Department API
  - AOS Weather Station data
  - Third-party data sources
  - Webhook endpoints

## Environment Setup

```bash
# Copy this to start your instance
cd /Users/subhajlimanond/dev/munbon2-backend

# Unified API runs from sensor-data service
cp services/sensor-data/.env.local.example services/sensor-data/.env.local

# Add external API specific configs
echo "
# External API Configuration
API_PORT=3000
API_KEY_HEADER=x-api-key
RATE_LIMIT_WINDOW=900000
RATE_LIMIT_MAX=100
CACHE_TTL=300
" >> services/sensor-data/.env.local
```

## Key Configurations

### API Authentication
```env
# API Keys (store securely in production)
API_KEYS=key1:client1,key2:client2
ENABLE_API_KEY_AUTH=true
ALLOW_ANONYMOUS=false
```

### Data Sources
```env
# Internal service URLs
SENSOR_SERVICE_URL=http://localhost:3003
GIS_SERVICE_URL=http://localhost:3007
ROS_SERVICE_URL=http://localhost:3047
WATER_LEVEL_SERVICE_URL=http://localhost:3008
```

### External APIs
```env
# Thai Meteorological Dept
TMD_API_URL=https://api.tmd.go.th
TMD_API_KEY=your-tmd-key

# AOS Weather
AOS_WEATHER_URL=http://www.aos-weather.com
AOS_STATION_ID=your-station-id
```

## API Endpoints Structure

### Public Endpoints (No Auth)
```
GET /health
GET /api/v1/status
```

### Authenticated Endpoints
```
# Sensor Data
GET /api/v1/sensors/water-level/latest
GET /api/v1/sensors/water-level/timeseries?date={date}
GET /api/v1/sensors/moisture/latest
GET /api/v1/sensors/aos/latest

# GIS Data
GET /api/v1/zones
GET /api/v1/parcels?zone={zoneId}
GET /api/v1/maps/tiles/{z}/{x}/{y}

# Analytics
GET /api/v1/analytics/water-demand
GET /api/v1/analytics/irrigation-schedule
```

## Current Status
- ✅ Basic unified API structure
- ✅ AWS Lambda deployment
- ✅ API key authentication
- ⚠️ Rate limiting: Basic implementation
- ⚠️ Caching: Redis integration needed
- ❌ API Gateway: Not configured
- ❌ Monitoring: Not implemented

## Priority Tasks
1. Implement comprehensive caching strategy
2. Add request/response logging
3. Set up Kong API Gateway
4. Create API documentation portal
5. Implement webhook system
6. Add GraphQL endpoint
7. Set up API versioning strategy

## API Response Format
```json
{
  "success": true,
  "data": {
    // Response data
  },
  "meta": {
    "timestamp": "2024-07-08T10:30:00Z",
    "version": "1.0.0",
    "count": 100
  }
}
```

## Error Response Format
```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests",
    "details": {
      "limit": 100,
      "window": "15 minutes",
      "retry_after": 900
    }
  }
}
```

## Testing Commands
```bash
# Test public endpoint
curl http://localhost:3000/health

# Test with API key
curl -H "x-api-key: test-key" \
  http://localhost:3000/api/v1/sensors/water-level/latest

# Test rate limiting
for i in {1..150}; do 
  curl -H "x-api-key: test-key" http://localhost:3000/api/v1/status
done

# Test data aggregation
curl -H "x-api-key: test-key" \
  "http://localhost:3000/api/v1/dashboard/summary?date=08/07/2568"
```

## Key Files to Focus On
- `/services/sensor-data/src/unified-api.js`
- `/services/sensor-data/src/routes/external-public.routes.ts`
- `/services/sensor-data/src/middleware/enhanced-api-auth.ts`
- `/api-contracts/openapi/unified-api-service.yaml`
- `/infrastructure/kong/kong.yml`

## Caching Strategy
```javascript
// Redis cache keys
"api:water-level:latest" -> 5 min TTL
"api:zones:list" -> 1 hour TTL  
"api:parcels:{zoneId}" -> 30 min TTL
"api:analytics:demand:{date}" -> 1 hour TTL
```

## Rate Limiting Tiers
```
Free Tier: 100 requests/15 min
Basic: 1000 requests/15 min
Premium: 10000 requests/15 min
Enterprise: Unlimited
```

## API Gateway Routes (Kong)
```yaml
services:
  - name: unified-api
    url: http://localhost:3000
    routes:
      - name: api-v1
        paths:
          - /api/v1
        methods:
          - GET
          - POST
    plugins:
      - name: key-auth
      - name: rate-limiting
        config:
          minute: 100
      - name: cors
```

## Notes for Development
- Always version APIs properly
- Implement idempotency for POST requests
- Use ETags for caching
- Add pagination for list endpoints
- Implement field filtering (?fields=id,name)
- Add comprehensive API documentation
- Monitor API usage and performance
- Implement request ID tracking