# Multi-Claude Development Guide for Munbon Backend

## Overview
This guide helps coordinate multiple Claude instances working on different microservices simultaneously.

## Service Assignments

### Instance 1: Core Services
- **Auth Service** (Port 3001) - `/services/auth`
- **User Management** - Related to auth
- **API Gateway Configuration**

### Instance 2: Data Services  
- **Sensor Data Service** (Port 3003) - `/services/sensor-data`
- **Water Level Monitoring** (Port 3008) - `/services/water-level-monitoring`
- **Moisture Monitoring** (Port 3005) - `/services/moisture-monitoring`

### Instance 3: GIS & Analytics
- **GIS Service** (Port 3007) - `/services/gis`
- **RID-MS Service** (Port 3009) - `/services/rid-ms`
- **Analytics Service** - `/services/analytics`

### Instance 4: Integration Services
- **Weather Monitoring** (Port 3006) - `/services/weather-monitoring`
- **SCADA Integration** - `/services/scada`
- **ROS Service** (Port 3047) - `/services/ros`

## Coordination Rules

### 1. **Port Allocation**
Each instance should only use assigned ports:
```
3001-3010: Core Services
3011-3020: Data Services  
3021-3030: GIS Services
3031-3040: Integration Services
3041-3050: Supporting Services
```

### 2. **Shared Resources**

#### Databases (Read-only for all, coordinate writes)
- PostgreSQL (5434) - Shared by all
- TimescaleDB (5433) - Sensor data only
- MongoDB (27017) - Document storage
- Redis (6379) - Cache/sessions

#### Message Queue
- Kafka (9092) - Coordinate topic creation
- Use service-specific topics: `auth.events`, `sensor.data`, etc.

### 3. **API Contracts**
- All instances must follow `/api-contracts/` specifications
- Don't modify contracts without coordination
- Use existing schemas in `/api-contracts/openapi/`

### 4. **Git Workflow**

#### Branch Naming
```
feature/auth-oauth-implementation
feature/gis-postgis-integration
feature/sensor-data-pipeline
```

#### Commit Messages
```
[Auth] Add OAuth 2.0 login flow
[GIS] Implement PostGIS spatial queries
[Sensor] Add MQTT data ingestion
```

### 5. **Communication Patterns**

#### Service Discovery
All services register at startup:
```javascript
// Register with service registry
await serviceRegistry.register({
  name: 'auth-service',
  port: 3001,
  health: '/health'
});
```

#### Inter-Service Communication
Use predefined interfaces:
```javascript
// From GIS service calling Auth
const authClient = new AuthServiceClient({
  baseURL: 'http://localhost:3001'
});
```

## Shared Configuration

### Environment Variables
Create `.env.local` for each service:
```bash
# services/auth/.env.local
SERVICE_NAME=auth-service
PORT=3001
DB_HOST=localhost
DB_PORT=5434

# services/gis/.env.local  
SERVICE_NAME=gis-service
PORT=3007
DB_HOST=localhost
DB_PORT=5434
```

### Docker Network
All services use the same network:
```yaml
networks:
  munbon-network:
    external: true
```

## Testing Coordination

### 1. **Integration Tests**
- Run after both services are ready
- Use shared test data in `/test/fixtures/`
- Tag tests by dependency: `@requires-auth`, `@requires-gis`

### 2. **Mock Services**
When service isn't ready, use mocks:
```javascript
// Mock auth service for GIS development
if (process.env.MOCK_AUTH) {
  app.use('/auth', mockAuthMiddleware);
}
```

## Common Issues & Solutions

### Port Conflicts
```bash
# Check port usage
lsof -i :3001

# Kill process if needed
kill -9 <PID>
```

### Database Migrations
- Coordinate schema changes
- Run migrations in order:
  1. Core services first
  2. Dependent services after

### Kafka Topics
- Create topics before using:
```bash
# Create topic for service
kafka-topics.sh --create --topic sensor.data --partitions 3
```

## Daily Sync Points

### Morning Standup (via Slack/Comments)
1. What service are you working on?
2. Any shared resource changes?
3. Any blocking dependencies?

### Before Major Changes
- Database schema modifications
- API contract updates
- Shared library changes
- Configuration updates

## Quick Reference

### Start All Dependencies
```bash
# Start infrastructure
docker-compose up -d postgres mongo redis kafka

# Start your service
cd services/your-service
npm run dev
```

### Check Service Health
```bash
# Check all services
curl http://localhost:3001/health  # Auth
curl http://localhost:3007/health  # GIS
curl http://localhost:3003/health  # Sensor
```

### View Logs
```bash
# PM2 logs
pm2 logs auth-service

# Docker logs  
docker logs munbon-postgres -f
```

## Tips for Success

1. **Keep services loosely coupled**
2. **Use async messaging for non-critical communication**
3. **Implement circuit breakers for service calls**
4. **Always provide health endpoints**
5. **Document your service's API changes**
6. **Test with other services regularly**

Remember: Microservices are about independent development and deployment!