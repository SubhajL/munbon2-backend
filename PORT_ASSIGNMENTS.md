# Port Assignments for Munbon Backend Services

## Fixed Port Conflict
Previously, Weather Monitoring and ROS Service both used port 3047. This has been fixed.

## Current Port Assignments

| Service | Port | Type | Description |
|---------|------|------|-------------|
| **Unified API** | 3000 | API | Simple data retrieval API |
| **Auth Service** | 3001 | API | Authentication & Authorization |
| **Sensor Data Service** | 3003 | API | Main sensor data ingestion |
| **Sensor Data Consumer** | 3004 | Dashboard | Consumer monitoring dashboard |
| **Moisture Monitoring** | 3005 | API | Moisture analytics service |
| **Weather Monitoring** | 3006 | API | Weather analytics service (changed from 3047) |
| **GIS Service** | 3007 | API | Spatial data operations |
| **Water Level Monitoring** | 3008 | API | Water level analytics service |
| **AWD Control Service** | 3010 | API | Alternate Wetting and Drying control |
| **Flow Monitoring Service** | 3011 | API | Hydraulic flow/volume/level monitoring |
| **ROS Service** | 3047 | API | Runoff Observation System |

## Background Workers (No Ports)
- GIS Queue Processor
- External Tunnel Monitor
- Tunnel Monitor

## Changes Made
1. **Weather Monitoring**: Changed from port 3047 → 3006 (to avoid conflict with ROS)
2. **Water Level Monitoring**: Changed from 3046 → 3008 (port 3004 is used by Sensor Consumer Dashboard)
3. **Moisture Monitoring**: Changed from 3044 → 3005

## Running Services

### Start all monitoring services:
```bash
pm2 start pm2-monitoring-services.config.js
```

### Start specific service:
```bash
pm2 start water-level-monitoring
pm2 start moisture-monitoring
pm2 start weather-monitoring
pm2 start ros-service
```

## Verification
To verify no port conflicts:
```bash
# Check which services are using which ports
lsof -i :3000-3050 | grep LISTEN
```

## Notes
- Sensor Data Consumer uses port 3004 for its monitoring dashboard
- All services can be configured via environment variables to use different ports if needed
- Each service has a unique port assignment to avoid conflicts