# Service Port Reference - Munbon Backend

## Confirmed Service Ports

Based on the codebase analysis, here are the confirmed service ports:

### Core Microservices

| Service | Port | Status | Location/Config |
|---------|------|--------|-----------------|
| **API Gateway (Unified API)** | 3000 | ✅ Active | pm2-ecosystem.config.js |
| **Auth Service** | 3001 | 🔲 Disabled | pm2-ecosystem.config.js (commented) |
| **Sensor Data Service** | 3003 | ✅ Active | pm2-ecosystem.config.js |
| **Sensor Consumer** | 3004 | ✅ Active | pm2-ecosystem.config.js |
| **GIS Service** | 3007 | ✅ Active | pm2-ecosystem.config.js |
| **Water Level Monitoring** | 3008 | ❓ Documented | CLAUDE_INSTANCE_2_WATER_LEVEL.md |
| **AWD Control Service** | 3010 | 📄 Planned | CLAUDE_INSTANCE_11_AWD_CONTROL.md |
| **Flow Monitoring Service** | 3011 | 📄 Planned | CLAUDE_INSTANCE_12_FLOW_MONITORING.md |
| **SCADA Integration Service** | 3015 | ✅ Active | pm2-ecosystem.config.js |
| **Sensor Location Mapping** | 3018 | ✅ Active | pm2-ecosystem.config.js |
| **Water Accounting Service** | 3019 | 📄 Planned | CLAUDE_INSTANCE_14_WATER_ACCOUNTING.md |
| **Scheduler Service** | 3021 | 📄 Planned | CLAUDE_INSTANCE_17_INIT_PROMPT.txt |
| **ROS/GIS Integration** | 3022 | ✅ Active | CLAUDE_INSTANCE_18_ROS_GIS_INTEGRATION.md |
| **Sensor Network Management** | 3023 | ✅ Active | services/sensor-network-management (Python/FastAPI) |
| **Irrigation Control** | 3025 | 📄 Planned | CLAUDE_INSTANCE_15_INIT_PROMPT.txt |
| **Moisture Monitoring** | 3044 | 📄 Config | services/moisture-monitoring/.env.example |
| **Water Level Monitoring** | 3046 | 📄 Config | services/water-level-monitoring/.env.example |
| **ROS Service** | 3047 | ✅ Confirmed | services/ros/src/config/index.ts |
| **RID-MS Service** | 3048 | 📄 Config | services/rid-ms/src/config/index.ts |
| **Mock Server (Testing)** | 3099 | 🧪 Test | Multiple references |

### Database Ports

| Database | Port | Purpose |
|----------|------|---------|
| PostgreSQL (Main) | 5432 | Primary database |
| TimescaleDB | 5433 | Time-series data |
| PostgreSQL (Dev) | 5434 | Development database |
| MongoDB | 27017 | Document storage |
| Redis | 6379 | Caching & sessions |
| InfluxDB | 8086 | Metrics (planned) |

## Port Corrections Needed

Based on my documentation vs actual codebase:

1. **ROS Service**: 
   - My documentation: Port 3047 ✅ CORRECT
   - Actual: Port 3047

2. **GIS Service**: 
   - My documentation: Port 3007 ✅ CORRECT
   - Actual: Port 3007

3. **ROS/GIS Integration**: 
   - My documentation: Port 3022 ✅ CORRECT
   - Actual: Port 3022

4. **Flow Monitoring**: 
   - My documentation: Port 3011 ✅ CORRECT
   - Actual: Port 3011 (planned)

5. **Scheduler Service**: 
   - My documentation: Port 3021 ✅ CORRECT
   - Actual: Port 3021 (planned)

## Summary

All service ports in my documentation are **CORRECT** and match the codebase references:
- ✅ ROS Service: 3047
- ✅ GIS Service: 3007
- ✅ ROS/GIS Integration: 3022
- ✅ Flow Monitoring: 3011
- ✅ Scheduler: 3021

## Service Communication Example

```bash
# ROS/GIS Integration calling ROS Service
curl http://localhost:3047/api/v1/water-demand/calculate

# ROS/GIS Integration calling GIS Service
curl http://localhost:3007/api/v1/parcels

# Scheduler calling ROS/GIS Integration
curl http://localhost:3022/graphql

# ROS/GIS Integration calling Flow Monitoring
curl http://localhost:3011/api/v1/gates/state
```