# Kong API Gateway Configuration

This directory contains the Kong API Gateway configuration for the Munbon Backend system.

## Overview

Kong is deployed as the main API Gateway to:
- Route requests to appropriate microservices
- Handle authentication and authorization
- Implement rate limiting (10,000+ concurrent connections)
- Provide API versioning
- Enable monitoring and analytics
- Manage SSL termination

## Architecture

```
Client → Kong Gateway (port 8000) → Microservices
           ↓
      Authentication
      Rate Limiting
      CORS
      Monitoring
```

## Services

The following services are configured in Kong:

| Service | Port | Description |
|---------|------|-------------|
| auth-service | 3001 | Authentication & Authorization |
| sensor-data-service | 3002 | IoT Sensor Data |
| gis-service | 3003 | GIS & Spatial Data |
| user-management-service | 3004 | User Management |
| weather-service | 3005 | Weather Integration |
| scada-service | 3006 | SCADA Integration |
| water-control-service | 3007 | Water Distribution Control |
| ai-model-service | 3008 | AI/ML Models |
| notification-service | 3009 | Notifications |
| reporting-service | 3010 | Reports Generation |

## Plugins

### Global Plugins
- **CORS**: Cross-Origin Resource Sharing
- **Rate Limiting**: 10,000 requests/hour (configurable by tier)
- **Request Size Limiting**: 10MB max payload
- **Prometheus**: Metrics collection
- **Bot Detection**: Block crawlers and scrapers

### Custom Plugins
1. **Thai Digital ID**: Integration with Thai government OAuth 2.0
2. **Tiered Rate Limiting**: Different limits based on user roles

## Quick Start

1. Start Kong with Docker Compose:
```bash
make up-kong
```

2. Check Kong health:
```bash
make kong-health
```

3. Access Kong services:
- Gateway: http://localhost:8000
- Admin API: http://localhost:8001
- Kong Manager: http://localhost:8002
- Konga Dashboard: http://localhost:1337

## API Routes

All APIs follow the pattern: `/api/v1/{service}/{resource}`

Examples:
- POST `/api/v1/auth/login`
- GET `/api/v1/sensors/moisture`
- GET `/api/v1/gis/tiles/{z}/{x}/{y}`
- POST `/api/v1/water-control/gates/{id}/operate`

## Authentication

Protected routes require JWT tokens in the Authorization header:
```
Authorization: Bearer <jwt-token>
```

Public routes:
- `/api/v1/auth/login`
- `/api/v1/auth/register`
- `/api/v1/auth/oauth/*`

## Rate Limiting Tiers

| Tier | Requests/min | Requests/hour | Requests/day |
|------|--------------|---------------|--------------|
| Guest | 10 | 100 | 1,000 |
| Basic | 60 | 1,000 | 10,000 |
| Premium | 200 | 5,000 | 50,000 |
| Enterprise | 1,000 | 20,000 | 200,000 |
| Government | 2,000 | 50,000 | 500,000 |

## Development

### Adding a New Service

1. Add service definition to `kong.yml`
2. Create routes in `kong.yml`
3. Run setup script: `bash scripts/setup-kong.sh`

### Testing API Calls

```bash
# Public endpoint
curl http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "test"}'

# Protected endpoint
curl http://localhost:8000/api/v1/sensors/moisture \
  -H "Authorization: Bearer <token>"

# With API Key
curl http://localhost:8000/api/v1/sensors/data \
  -H "apikey: iot-dev-key-change-in-production"
```

## Monitoring

### Prometheus Metrics
Available at: http://localhost:8001/metrics

### Health Checks
- Kong Status: http://localhost:8001/status
- Service Health: Configured per service with active health checks

### Logs
View Kong logs:
```bash
docker logs munbon-kong -f
```

## Security

1. **SSL/TLS**: Configure certificates for production
2. **IP Restriction**: Enable for production environments
3. **API Keys**: Rotate regularly
4. **JWT Secrets**: Use strong secrets in production
5. **Thai Digital ID**: Configure OAuth credentials

## Troubleshooting

### Kong not starting
```bash
# Check logs
docker logs munbon-kong

# Verify database migration
docker logs munbon-kong-migration
```

### Route not found
```bash
# List all routes
curl http://localhost:8001/routes

# Check specific service
curl http://localhost:8001/services/{service-name}
```

### Authentication issues
```bash
# Check JWT plugin
curl http://localhost:8001/plugins

# Verify consumer
curl http://localhost:8001/consumers/{username}
```