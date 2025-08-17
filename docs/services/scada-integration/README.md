# SCADA Integration Service

The SCADA Integration Service provides a centralized API for monitoring and controlling SCADA systems in the Munbon Irrigation Control System.

## Overview

This service acts as the bridge between the Munbon system and the SCADA infrastructure (GE iFix), providing:
- Real-time health monitoring of SCADA sites
- Gate control command execution
- Command status tracking
- Site availability monitoring

## Port

- **Service Port**: 3015

## API Endpoints

### Health Monitoring

#### Get SCADA Health Status
```
GET /api/v1/scada/health
```

Returns overall SCADA system health:
```json
{
  "status": "healthy",
  "totalSites": 20,
  "onlineSites": 18,
  "offlineSites": 2,
  "staleDataSites": 1,
  "lastCheck": "2024-01-15T10:30:00Z"
}
```

#### Get Detailed Health Status
```
GET /api/v1/scada/health/detailed
```

Returns detailed status for each site including:
- Site status (ONLINE/OFFLINE)
- Last update time
- Data freshness

#### Get Site Status
```
GET /api/v1/scada/sites/status
GET /api/v1/scada/sites/:stationCode/status
```

### Gate Control

#### Send Gate Command
```
POST /api/v1/scada/command/send
```

Request body:
```json
{
  "gate_name": "G001",
  "gate_level": 2,
  "fieldId": "field-123",
  "targetFlowRate": 5.5
}
```

Gate levels:
- 1 = Closed
- 2 = Level 1 (partially open)
- 3 = Level 2 (more open)
- 4 = Level 3 (fully open)

#### Check Command Status
```
GET /api/v1/scada/command/:id/status
```

#### Get Recent Commands
```
GET /api/v1/scada/commands/recent?limit=50
```

#### Get Pending Commands
```
GET /api/v1/scada/commands/pending
```

#### Convenience Endpoints
```
POST /api/v1/scada/gates/:gateName/close
POST /api/v1/scada/gates/:gateName/open
```

## Database

The service connects to the SCADA database:
- Host: moonup.hopto.org (43.209.22.250)
- Database: db_scada
- Tables:
  - `tb_site`: Site information and status
  - `tb_gatelevel_command`: Gate control commands

## Health Monitoring Logic

Site health is evaluated based on:
- **laststatus**: ONLINE or OFFLINE
- **dt_laststatus**: Timestamp of last update

Health status levels:
- **HEALTHY**: All sites ONLINE with recent updates (< 5 minutes)
- **DEGRADED**: Some sites OFFLINE or stale data (5-15 minutes)
- **CRITICAL**: Many sites OFFLINE or very stale data (> 15 minutes)  
- **FAILED**: Cannot connect to database or all sites OFFLINE

## Environment Variables

```bash
PORT=3015
SCADA_DB_HOST=moonup.hopto.org
SCADA_DB_PORT=5432
SCADA_DB_NAME=db_scada
SCADA_DB_USER=postgres
SCADA_DB_PASSWORD=P@ssw0rd123!
```

## Development

```bash
# Install dependencies
npm install

# Run in development mode
npm run dev

# Build for production
npm run build

# Run production build
npm start
```

## Docker

```bash
# Build image
docker build -t scada-integration-service .

# Run container
docker run -p 3015:3015 \
  -e SCADA_DB_HOST=moonup.hopto.org \
  -e SCADA_DB_PASSWORD=P@ssw0rd123! \
  scada-integration-service
```

## Integration with Other Services

### AWD Control Service
The AWD Control service can use this service instead of direct SCADA database connection:
- Import `scadaApiService` from the AWD Control service
- Use API calls instead of direct database queries
- Monitor SCADA health through `/api/v1/awd/scada/health` endpoint

### Flow Monitoring Service
Update the SCADA service URL from expected to actual:
```
http://scada-integration:3015
```

## Monitoring

The service provides:
- Health check endpoint at `/health`
- Automatic monitoring of gate commands every 30 seconds
- Caching of health status for 30 seconds to reduce database load

## Security

- Uses environment variables for sensitive configuration
- Supports Bearer token authentication (optional)
- Runs as non-root user in Docker container
- Implements proper error handling and logging