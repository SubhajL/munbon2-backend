# Service-Specific Environment Configuration Guide

## Overview

Each microservice has its own `.env.local` file for configuration isolation. This allows:
- Independent configuration per service
- No conflicts between services
- Easy local development with multiple Claude instances
- Service-specific secrets and settings

## Structure

```
munbon2-backend/
├── .env.shared.example      # Shared vars across all services
├── services/
│   ├── auth/
│   │   ├── .env.local.example   # Template
│   │   └── .env.local          # Actual config (git ignored)
│   ├── sensor-data/
│   │   ├── .env.local.example
│   │   └── .env.local
│   ├── gis/
│   │   ├── .env.local.example
│   │   └── .env.local
│   └── ...
```

## Quick Setup

### For New Service
```bash
# 1. Create .env.local from template
cd services/your-service
cp .env.local.example .env.local

# 2. Or use the setup script
./scripts/setup-service-env.sh your-service
```

### For Existing Service
```bash
# Check if .env.local exists
ls services/auth/.env.local

# If not, create from example
cp services/auth/.env.local.example services/auth/.env.local
```

## Environment Loading Priority

1. **Service-specific .env.local** (highest priority)
2. **Shared .env.shared** (common values)
3. **Default values in code** (fallback)

```javascript
// Example in service code
require('dotenv').config({ path: '.env.local' });
require('dotenv').config({ path: '../../.env.shared' });

const port = process.env.PORT || 3000;
```

## Port Allocation

Each service has a designated port to avoid conflicts:

| Service | Port | Description |
|---------|------|-------------|
| Auth | 3001 | Authentication & Authorization |
| User Management | 3002 | User profiles & permissions |
| Sensor Data | 3003 | IoT data ingestion |
| Consumer Dashboard | 3004 | Real-time consumer stats |
| Moisture Monitoring | 3005 | Soil moisture analytics |
| Weather Monitoring | 3006 | Weather data processing |
| GIS | 3007 | Spatial data operations |
| Water Level | 3008 | Water level analytics |
| RID-MS | 3009 | RID Management System |
| Notification | 3010 | Multi-channel notifications |

## Database Schemas

Each service typically uses its own schema/database:

```sql
-- PostgreSQL schemas
CREATE SCHEMA auth_service;
CREATE SCHEMA gis_service;
CREATE SCHEMA water_control;

-- Or separate databases
CREATE DATABASE munbon_auth;
CREATE DATABASE munbon_gis;
CREATE DATABASE munbon_sensors;
```

## Example Configurations

### Auth Service (.env.local)
```bash
# Override shared values
PORT=3001
DB_NAME=munbon_auth
REDIS_DB=0

# Service-specific
JWT_SECRET=dev-secret-auth-2024
OAUTH_CALLBACK_URL=http://localhost:3001/callback
```

### GIS Service (.env.local)
```bash
# Override shared values
PORT=3007
DB_NAME=munbon_gis
REDIS_DB=2

# Service-specific
MAPBOX_TOKEN=pk.test.xyz
MAX_UPLOAD_SIZE=100MB
SPATIAL_INDEX=true
```

### Sensor Data Service (.env.local)
```bash
# Override shared values
PORT=3003
DB_HOST=localhost
DB_PORT=5433  # TimescaleDB
REDIS_DB=1

# Service-specific
MQTT_BROKER=mqtt://localhost:1883
BATCH_SIZE=1000
DATA_RETENTION_DAYS=365
```

## Security Best Practices

### 1. Never Commit .env.local
```bash
# Always in .gitignore
.env.local
.env.*.local
```

### 2. Use Different Secrets Per Service
```bash
# Bad - same secret everywhere
JWT_SECRET=my-secret

# Good - service-specific
AUTH_JWT_SECRET=auth-secret-2024
GIS_API_KEY=gis-key-2024
SENSOR_MQTT_PASS=sensor-pass-2024
```

### 3. Rotate Secrets Regularly
```bash
# Development secrets - rotate monthly
# Production secrets - rotate quarterly
# Use timestamp in secret for tracking
JWT_SECRET=dev-auth-202407
```

## Working with Multiple Claude Instances

### Instance 1 (Auth Service)
```bash
# Terminal 1
cd services/auth
# Uses services/auth/.env.local
npm run dev  # Runs on port 3001
```

### Instance 2 (GIS Service)
```bash
# Terminal 2
cd services/gis
# Uses services/gis/.env.local
npm run dev  # Runs on port 3007
```

### Instance 3 (Sensor Service)
```bash
# Terminal 3
cd services/sensor-data
# Uses services/sensor-data/.env.local
npm run dev  # Runs on port 3003
```

## Troubleshooting

### Port Already in Use
```bash
# Check which service is using the port
lsof -i :3001

# Each service should use its assigned port from .env.local
```

### Environment Not Loading
```javascript
// Check load order in service
console.log('PORT:', process.env.PORT);
console.log('DB_HOST:', process.env.DB_HOST);

// Verify file exists
ls -la .env.local
```

### Wrong Configuration Loaded
```bash
# Check for multiple .env files
find . -name ".env*" -type f

# Ensure loading correct file
NODE_ENV=development npm run dev
```

## Inter-Service Communication

Services should use environment variables for other service URLs:

```javascript
// In GIS service .env.local
AUTH_SERVICE_URL=http://localhost:3001
SENSOR_SERVICE_URL=http://localhost:3003

// In code
const authAPI = process.env.AUTH_SERVICE_URL;
const response = await fetch(`${authAPI}/verify`);
```

## Docker Considerations

When using Docker, override with docker-compose:

```yaml
services:
  auth:
    env_file:
      - ./services/auth/.env.local
    environment:
      - DB_HOST=postgres  # Override for container
  
  gis:
    env_file:
      - ./services/gis/.env.local
    environment:
      - DB_HOST=postgres
```

## Summary

- Each service has independent `.env.local`
- No sharing of sensitive configs between services
- Clear port allocation prevents conflicts
- Multiple Claude instances can work independently
- Git ignores all `.env.local` files for security