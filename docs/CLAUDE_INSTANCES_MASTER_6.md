# Claude Instances Master Coordination (6 Instances)

## Overview
Six specialized Claude instances working on different aspects of the Munbon irrigation system.

## Instance Summary

| Instance | Focus Area | Primary Services | Ports | Status |
|----------|------------|------------------|--------|---------|
| 1 | AOS Weather | Weather monitoring, TMD integration | 3003, 3006 | 🟡 Development |
| 2 | Water Level | Water sensors, flow calculations | 3003, 3008 | 🟢 Active |
| 3 | Moisture | Soil sensors, irrigation detection | 3003, 3005 | 🟢 Active |
| 4 | SHAPE/GIS | Spatial data, PostGIS operations | 3007, 3009 | 🟡 Development |
| 5 | External API | Public API, data aggregation | 3000, 8000 | 🟢 Active |
| 6 | ROS | Water demand, ETo calculations | 3047 | 🔴 Planning |

## Quick Instance Setup

### Opening New Claude Windows

Copy and paste these exact initialization messages:

#### Instance 1 - AOS Weather:
```
I'm working on the AOS Weather Data services of the Munbon backend project.
Project path: /Users/subhajlimanond/dev/munbon2-backend
Please read CLAUDE_INSTANCE_1_AOS_WEATHER.md for my scope.
I'll handle weather station data, meteorological APIs, and weather analytics.
My services: weather monitoring (3006) and weather data ingestion via sensor-data (3003).
```

#### Instance 2 - Water Level:
```
I'm working on the Water Level Monitoring services of the Munbon backend project.
Project path: /Users/subhajlimanond/dev/munbon2-backend
Please read CLAUDE_INSTANCE_2_WATER_LEVEL.md for my scope.
I'll handle water level sensors, flow calculations, and flood/drought warnings.
My services: water level monitoring (3008) and water sensor ingestion via sensor-data (3003).
```

#### Instance 3 - Moisture:
```
I'm working on the Moisture Monitoring services of the Munbon backend project.
Project path: /Users/subhajlimanond/dev/munbon2-backend
Please read CLAUDE_INSTANCE_3_MOISTURE.md for my scope.
I'll handle soil moisture sensors, multi-layer analysis, and irrigation recommendations.
My services: moisture monitoring (3005) and moisture sensor ingestion via sensor-data (3003).
```

#### Instance 4 - SHAPE/GIS:
```
I'm working on the SHAPE/GIS services of the Munbon backend project.
Project path: /Users/subhajlimanond/dev/munbon2-backend
Please read CLAUDE_INSTANCE_4_SHAPE_GIS.md for my scope.
I'll handle SHAPE file processing, PostGIS operations, and spatial analysis.
My services: GIS service (3007) and RID-MS integration (3009).
```

#### Instance 5 - External API:
```
I'm working on the External Data API of the Munbon backend project.
Project path: /Users/subhajlimanond/dev/munbon2-backend
Please read CLAUDE_INSTANCE_5_EXTERNAL_API.md for my scope.
I'll manage the unified API, data aggregation, and external client interfaces.
My services: unified API (3000) and API gateway configuration (8000).
```

#### Instance 6 - ROS:
```
I'm working on the ROS Service of the Munbon backend project.
Project path: /Users/subhajlimanond/dev/munbon2-backend
Please read CLAUDE_INSTANCE_6_ROS.md for my scope.
I'll implement water demand calculations, ETo algorithms, and irrigation scheduling.
My service: ROS calculations (3047).
```

## Service Dependencies Graph

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Instance 1    │     │   Instance 2    │     │   Instance 3    │
│  AOS Weather    │     │  Water Level    │     │   Moisture      │
│    (3006)       │     │    (3008)       │     │    (3005)       │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                         │
         └───────────────────────┴─────────────────────────┘
                                 │
                                 ↓
                        ┌─────────────────┐
                        │   TimescaleDB   │
                        │     (5433)      │
                        └────────┬────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ↓                       ↓                       ↓
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Instance 6    │     │   Instance 5    │     │   Instance 4    │
│      ROS        │←────│  External API   │────→│   SHAPE/GIS     │
│    (3047)       │     │    (3000)       │     │  (3007,3009)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                                                         ↓
                                                 ┌─────────────────┐
                                                 │    PostGIS      │
                                                 │     (5434)      │
                                                 └─────────────────┘
```

## Data Flow Patterns

### Sensor Data Flow (Instances 1, 2, 3)
```
IoT Devices → MQTT/HTTP → Sensor Data Service → SQS Queues → Consumers → TimescaleDB
                                                      ↓
                              Weather Queue  → Weather Monitoring (Instance 1)
                              Water Queue    → Water Monitoring (Instance 2)  
                              Moisture Queue → Moisture Monitoring (Instance 3)
```

### API Aggregation Flow (Instance 5)
```
Client Request → External API → Parallel Fetch → Response Assembly → Client
                      ↓
              ┌───────┴───────┬───────┬────────┬─────────┐
              │               │       │        │         │
         Weather API    Water API  Moisture  GIS API  ROS API
         (Inst 1)      (Inst 2)   (Inst 3)  (Inst 4) (Inst 6)
```

### Calculation Flow (Instance 6)
```
ROS Service ← Weather Data (Instance 1)
    ↓      ← Moisture Data (Instance 3)
    ↓      ← Parcel Data (Instance 4)
    ↓
Water Demand → Irrigation Schedule → External API (Instance 5)
```

## Port Allocation

### Sensor Services (Shared Port 3003)
- Instance 1: Weather data ingestion endpoints
- Instance 2: Water level data ingestion endpoints  
- Instance 3: Moisture data ingestion endpoints

### Analytics Services
- 3005: Moisture Monitoring (Instance 3)
- 3006: Weather Monitoring (Instance 1)
- 3008: Water Level Monitoring (Instance 2)

### GIS Services
- 3007: GIS Service (Instance 4)
- 3009: RID-MS Service (Instance 4)

### API Services
- 3000: Unified/External API (Instance 5)
- 3047: ROS Calculations (Instance 6)
- 8000: API Gateway Proxy (Instance 5)

## Database Responsibilities

| Database | Write Access | Read Access |
|----------|--------------|-------------|
| TimescaleDB (5433) | Instances 1,2,3 | Instances 5,6 |
| PostgreSQL (5434) | Instance 4,6 | Instance 5 |
| PostGIS (5434) | Instance 4 | Instances 5,6 |
| Redis (6379) | All instances | All instances |

### Redis Database Allocation
- DB 0: Auth/Sessions (shared)
- DB 1: Rate limiting (Instance 5)
- DB 2: GIS queue (Instance 4)
- DB 4: ROS cache (Instance 6)
- DB 5: Moisture cache (Instance 3)
- DB 6: Weather cache (Instance 1)
- DB 7: External API cache (Instance 5)
- DB 8: Water level cache (Instance 2)

## SQS Queue Assignments

| Queue Name | Producer | Consumer |
|------------|----------|----------|
| munbon-aos-weather-queue | Sensor API | Instance 1 |
| munbon-water-level-queue | Sensor API | Instance 2 |
| munbon-moisture-queue | Sensor API | Instance 3 |
| munbon-shape-upload-queue | GIS API | Instance 4 |

## Coordination Points

### 1. API Contract Updates
- Instance making change must update `/api-contracts/openapi/`
- Instance 5 (External API) must be notified
- Update mock server configurations

### 2. New Data Types
- Define schema in appropriate instance
- Update Instance 5 aggregation logic
- Add to API documentation

### 3. Cross-Instance Data Needs
- Instance 6 needs weather → Request from Instance 1
- Instance 6 needs parcels → Request from Instance 4
- Instance 5 needs all data → Read from all instances

### 4. Performance Optimization
- Instances 1,2,3: Optimize batch processing
- Instance 4: Optimize spatial queries
- Instance 5: Optimize caching strategy
- Instance 6: Optimize calculations

## Development Workflow

### Daily Standup Order
1. **Infrastructure Check** - All databases running?
2. **Instance 1,2,3** - Sensor data flowing?
3. **Instance 4** - Any SHAPE processing issues?
4. **Instance 6** - Calculation services ready?
5. **Instance 5** - API serving all data correctly?

### Testing Integration
```bash
# Test sensor data flow
curl -X POST http://localhost:3003/api/v1/telemetry \
  -d '{"type":"weather","data":{...}}'

# Test GIS query
curl http://localhost:3007/api/v1/parcels/P12345

# Test ROS calculation
curl http://localhost:3047/api/v1/ros/eto/calculate

# Test external API aggregation
curl http://localhost:3000/api/v1/dashboard/summary
```

## Common Commands

### Check All Services
```bash
#!/bin/bash
echo "=== Munbon Services Status ==="
curl -s http://localhost:3006/health || echo "❌ Weather"
curl -s http://localhost:3008/health || echo "❌ Water Level"
curl -s http://localhost:3005/health || echo "❌ Moisture"
curl -s http://localhost:3007/health || echo "❌ GIS"
curl -s http://localhost:3000/health || echo "❌ External API"
curl -s http://localhost:3047/health || echo "❌ ROS"
```

### Start Services by Instance
```bash
# Instance 1 (Weather)
cd services/weather-monitoring && npm run dev

# Instance 2 (Water)
cd services/water-level-monitoring && npm run dev

# Instance 3 (Moisture)
cd services/moisture-monitoring && npm run dev

# Instance 4 (GIS)
cd services/gis && npm run dev

# Instance 5 (API)
cd services/sensor-data && node src/unified-api.js

# Instance 6 (ROS)
cd services/ros && npm run dev
```

## Success Metrics

- **Instance 1**: Weather data updating every 5 minutes
- **Instance 2**: Water levels streaming in real-time
- **Instance 3**: Moisture profiles available for all fields
- **Instance 4**: SHAPE files processing < 5 minutes
- **Instance 5**: API response times < 200ms
- **Instance 6**: Water demand calculations < 1 second

## Remember
- Each instance has its own `.env.local`
- Don't modify shared resources without coordination
- Use instance-specific git branches
- Document API changes immediately
- Test integrations regularly