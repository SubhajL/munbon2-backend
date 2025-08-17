# Munbon Irrigation System API Contracts

This directory contains the comprehensive API contract definitions for all microservices in the Munbon Irrigation System.

## Structure

```
api-contracts/
├── openapi/              # OpenAPI 3.0 specifications
│   ├── auth-service.yaml
│   ├── sensor-data-service.yaml
│   ├── gis-service.yaml
│   ├── water-control-service.yaml
│   ├── rid-ms-service.yaml
│   └── ...
├── schemas/              # Shared JSON schemas
│   ├── common/
│   ├── sensor/
│   ├── control/
│   └── ...
└── examples/             # Request/response examples
    ├── auth/
    ├── sensor/
    └── ...
```

## API Standards

### 1. **REST API Design Principles**
- Use nouns for resources (e.g., `/sensors`, `/gates`)
- HTTP methods: GET (read), POST (create), PUT (update), DELETE (delete), PATCH (partial update)
- Plural resource names: `/api/v1/sensors` not `/api/v1/sensor`
- Nested resources: `/api/v1/zones/{zoneId}/sensors`

### 2. **Versioning**
- URL path versioning: `/api/v1/...`
- Major version in URL, minor version in headers
- Deprecation policy: 6 months notice

### 3. **Authentication**
- Bearer token in Authorization header
- API key for service-to-service communication
- OAuth 2.0 for third-party integrations

### 4. **Response Format**
```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "timestamp": "2024-06-20T10:30:00Z",
    "version": "1.0.0"
  }
}
```

### 5. **Error Format**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input parameters",
    "details": [
      {
        "field": "sensorId",
        "message": "Sensor ID must be a valid UUID"
      }
    ]
  },
  "meta": {
    "timestamp": "2024-06-20T10:30:00Z",
    "requestId": "req_123456"
  }
}
```

### 6. **Pagination**
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "perPage": 20,
    "total": 150,
    "totalPages": 8
  }
}
```

### 7. **Filtering & Sorting**
- Filter: `GET /api/v1/sensors?type=moisture&status=active`
- Sort: `GET /api/v1/sensors?sort=-createdAt,name`
- Search: `GET /api/v1/sensors?q=keyword`

### 8. **Rate Limiting Headers**
- `X-RateLimit-Limit`: Request limit
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Reset timestamp

### 9. **CORS Headers**
- Configured per service based on client requirements
- Preflight requests supported

### 10. **Content Types**
- Request: `application/json`
- Response: `application/json`
- File upload: `multipart/form-data`
- Streaming: `text/event-stream`

## Service Endpoints

### Gateway
- Base URL: `https://api.munbon.go.th`
- Health: `GET /health`
- Metrics: `GET /metrics`

### Core Services
1. **Authentication**: `/api/v1/auth/*`
2. **Sensor Data**: `/api/v1/sensors/*`
3. **Water Control**: `/api/v1/control/*`
4. **GIS**: `/api/v1/gis/*`
5. **Alerts**: `/api/v1/alerts/*`
6. **Reports**: `/api/v1/reports/*`
7. **RID-MS**: `/api/v1/rid-ms/*`, `/api/v1/parcels/*`, `/api/v1/zones/*`, `/api/v1/export/*`

## Development Tools

### Generate Documentation
```bash
# Generate HTML documentation
npm run docs:generate

# Validate OpenAPI specs
npm run docs:validate
```

### Mock Server
```bash
# Start mock server with examples
npm run mock:server
```

## Integration Guidelines

1. Always use the latest API contracts
2. Implement proper error handling
3. Include correlation IDs in requests
4. Log all API interactions
5. Implement retry logic with exponential backoff
6. Cache responses where appropriate

## Change Management

1. All API changes must be backwards compatible
2. Breaking changes require major version bump
3. Deprecation notices via headers
4. Migration guides for breaking changes