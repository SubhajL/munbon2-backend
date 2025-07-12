# Claude Instances Master Coordination

## Overview
Twelve specialized Claude instances working on different aspects of the Munbon irrigation system.

## Instance Summary

| Instance | Focus Area | Primary Services | Ports | Status |
|----------|------------|------------------|--------|---------|
| 1 | AOS Weather | Weather monitoring, TMD integration | 3003, 3006 | 🟡 Development |
| 2 | Water Level | Water sensors, flow calculations | 3003, 3008 | 🟢 Active |
| 3 | Moisture | Soil sensors, irrigation detection | 3003, 3005 | 🟢 Active |
| 4 | SHAPE/GIS | Spatial data, PostGIS operations | 3007, 3009 | 🟡 Development |
| 5 | External API | Public API, data aggregation | 3000, 8000 | 🟢 Active |
| 6 | ROS | Water demand, ETo calculations | 3047 | 🔴 Planning |
| 7 | Setup BFF | System setup, onboarding | 4001 | 🔴 Planning |
| 8 | Water Planning BFF | Irrigation planning, optimization | 4002 | 🔴 Planning |
| 9 | Water Control BFF | Real-time control, SCADA | 4003, 4103 | 🔴 Planning |
| 10 | Dashboard BFF | Data visualization, KPIs | 4004, 4104 | 🔴 Planning |
| 11 | AWD Control | AWD irrigation, water optimization | 3003, 3010 | 🔴 Planning |
| 12 | Flow Monitoring | Hydraulic monitoring, flow analytics | 3011, 8086 | 🔴 Planning |

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

#### Instance 7 - Setup BFF:
```
I'm working on the Setup BFF Service of the Munbon backend project.
Project path: /Users/subhajlimanond/dev/munbon2-backend
Please read CLAUDE_INSTANCE_7_SETUP_BFF.md for my scope.
I'll handle system setup, user onboarding, and initial configuration workflows.
My service: Setup BFF with GraphQL (4001).
```

#### Instance 8 - Water Planning BFF:
```
I'm working on the Water Planning BFF Service of the Munbon backend project.
Project path: /Users/subhajlimanond/dev/munbon2-backend
Please read CLAUDE_INSTANCE_8_WATER_PLANNING_BFF.md for my scope.
I'll handle irrigation planning, water allocation optimization, and scheduling.
My service: Water Planning BFF with GraphQL (4002).
```

#### Instance 9 - Water Control BFF:
```
I'm working on the Water Control BFF Service of the Munbon backend project.
Project path: /Users/subhajlimanond/dev/munbon2-backend
Please read CLAUDE_INSTANCE_9_WATER_CONTROL_BFF.md for my scope.
I'll handle real-time water control, gate operations, and SCADA integration.
My services: Water Control BFF (4003) with WebSocket (4103).
```

#### Instance 10 - Dashboard BFF:
```
I'm working on the Dashboard BFF Service of the Munbon backend project.
Project path: /Users/subhajlimanond/dev/munbon2-backend
Please read CLAUDE_INSTANCE_10_DASHBOARD_BFF.md for my scope.
I'll handle dashboard data aggregation, KPIs, and real-time visualizations.
My services: Dashboard BFF (4004) with WebSocket (4104).
```

#### Instance 11 - AWD Control:
```
I'm working on the AWD (Alternate Wetting and Drying) Control services of the Munbon backend project.
Project path: /Users/subhajlimanond/dev/munbon2-backend
Please read CLAUDE_INSTANCE_11_AWD_CONTROL.md for my scope.
I'll handle AWD irrigation control, water level thresholds, and automated gate operations for rice fields.
My services: AWD control service (3010) and AWD sensor integration via sensor-data (3003).
```

#### Instance 12 - Flow Monitoring:
```
I'm working on the Flow/Volume/Level Monitoring services of the Munbon backend project.
Project path: /Users/subhajlimanond/dev/munbon2-backend
Please read CLAUDE_INSTANCE_12_FLOW_MONITORING.md for my scope.
I'll handle hydraulic monitoring, flow calculations, water balance, and predictive analytics.
My services: Flow monitoring service (3011) using Python/FastAPI with InfluxDB and TimescaleDB.
```

## Service Architecture Overview

```
                           ┌─────────────────────────┐
                           │    Client Applications   │
                           └───────────┬─────────────┘
                                       │
                          ┌────────────┴────────────┐
                          │    BFF Layer (4001-4004)│
                          ├────────────────────────┤
                          │ Setup │ Planning │     │
                          │ Control │ Dashboard    │
                          └────────────┬───────────┘
                                       │
┌──────────────────────────────────────┴────────────────────────────────────────┐
│                          Core Services Layer                                   │
├──────────────┬──────────────┬──────────────┬──────────────┬──────────────────┤
│ Weather (1)  │ Water (2)    │ Moisture (3) │ GIS (4)      │ AWD Control (11) │
│ Port: 3006   │ Port: 3008   │ Port: 3005   │ Port: 3007   │ Port: 3010       │
├──────────────┴──────────────┴──────────────┴──────────────┼──────────────────┤
│         ROS (6)                    │    Flow Monitoring (12)                  │
│         Port: 3047                 │    Port: 3011                            │
└────────────────────────────────────┴──────────────────────────────────────────┘
                                       │
                          ┌────────────┴────────────┐
                          │   External API (5)     │
                          │      Port: 3000        │
                          └─────────────────────────┘
```

## Data Flow Patterns

### BFF Service Interactions

```
Setup BFF (7) → Creates initial configuration → All Services
                    ↓
Planning BFF (8) → Reads data from (1,2,3,4,6,11,12) → Creates plans
                    ↓
Control BFF (9) → Executes plans → Controls devices → Updates (2,3,11)
                    ↓
Dashboard BFF (10) → Aggregates from all → Displays to users
```

### Service Dependencies

| BFF Service | Depends On | Purpose |
|-------------|------------|---------|
| Setup BFF | Auth, GIS, Config | Initial system configuration |
| Planning BFF | ROS, Weather, GIS, Analytics | Water planning & optimization |
| Control BFF | SCADA, IoT, Water Level, Alerts | Real-time operations |
| Dashboard BFF | All services (read-only) | Data visualization |

## Port Allocation

### Data Services (3000s)
- 3000: External API
- 3003: Sensor Data (shared ingestion)
- 3005: Moisture Monitoring
- 3006: Weather Monitoring
- 3007: GIS Service
- 3008: Water Level Monitoring
- 3009: RID-MS Service
- 3010: AWD Control Service
- 3011: Flow Monitoring Service
- 3047: ROS Calculations

### BFF Services (4000s)
- 4001: Setup BFF (GraphQL)
- 4002: Water Planning BFF (GraphQL)
- 4003: Water Control BFF (GraphQL)
- 4004: Dashboard BFF (GraphQL)
- 4103: Water Control WebSocket
- 4104: Dashboard WebSocket

## Database Access Patterns

| Service | PostgreSQL | TimescaleDB | PostGIS | MongoDB | Redis |
|---------|------------|-------------|---------|---------|--------|
| Weather (1) | Read | Write | No | No | Cache |
| Water (2) | Read | Write | No | No | Cache |
| Moisture (3) | Read | Write | No | No | Cache |
| GIS (4) | Read/Write | No | Write | No | Cache |
| External API (5) | Read | Read | Read | Read | Cache |
| ROS (6) | Read/Write | Read | Read | No | Cache |
| Setup BFF (7) | Write | No | No | Write | Session |
| Planning BFF (8) | Read | Read | Read | Read | Cache |
| Control BFF (9) | Read | Read | No | No | State |
| Dashboard BFF (10) | Read | Read | Read | Read | Cache |
| AWD Control (11) | Read/Write | Write | No | No | State |
| Flow Monitoring (12) | Read | Write | No | No | Cache |

## Redis Database Allocation
- DB 0: Shared authentication/sessions
- DB 1: External API rate limiting
- DB 2: GIS processing queue
- DB 4: ROS calculation cache
- DB 5: Moisture data cache
- DB 6: Weather data cache
- DB 7: External API response cache
- DB 8: Water level data cache
- DB 9: Setup BFF sessions
- DB 10: Planning BFF cache
- DB 11: Control BFF state
- DB 12: Dashboard BFF cache
- DB 13: AWD Control state/cache
- DB 14: Flow Monitoring cache

## BFF-Specific Considerations

### GraphQL Federation
All BFF services expose GraphQL endpoints that can be federated:
```graphql
# Federation gateway at port 4000
type Query {
  # From Setup BFF
  setupProgress: SetupProgress @gateway(service: "setup")
  
  # From Planning BFF
  irrigationPlans: [IrrigationPlan] @gateway(service: "planning")
  
  # From Control BFF
  systemState: SystemState @gateway(service: "control")
  
  # From Dashboard BFF
  dashboards: [Dashboard] @gateway(service: "dashboard")
}
```

### WebSocket Connections
- Control BFF (4103): Real-time device control
- Dashboard BFF (4104): Live data streaming

### Authentication Flow
1. All BFF services validate JWT tokens
2. Role-based access per BFF:
   - Setup: ADMIN only
   - Planning: PLANNER, MANAGER, ADMIN
   - Control: OPERATOR, ADMIN
   - Dashboard: All authenticated users

## Development Guidelines

### For BFF Services
1. Use GraphQL with Apollo Server
2. Implement DataLoader for N+1 prevention
3. Add request-level caching
4. Support subscription for real-time
5. Implement field-level authorization
6. Use schema stitching for federation

### For Data Services
1. Focus on domain logic
2. Expose REST APIs
3. Implement efficient queries
4. Handle high-throughput data
5. Provide WebSocket for real-time

## Daily Coordination

### Morning Check
1. All 10 instances running?
2. Database connections healthy?
3. Redis memory usage OK?
4. Any overnight alerts?

### Integration Points
- Planning BFF needs latest weather → Check Instance 1
- Control BFF needs water levels → Check Instance 2
- Dashboard needs all data → Check all instances

### Common Issues
- Port conflicts: Check CLAUDE_INSTANCES_MASTER.md
- GraphQL schema conflicts: Check federation gateway
- WebSocket disconnections: Check network and timeouts
- Cache invalidation: Coordinate between instances

## Testing All Services

```bash
#!/bin/bash
echo "=== Munbon Services Health Check ==="

# Data Services
echo "Data Services:"
curl -s http://localhost:3006/health || echo "❌ Weather"
curl -s http://localhost:3008/health || echo "❌ Water Level"
curl -s http://localhost:3005/health || echo "❌ Moisture"
curl -s http://localhost:3007/health || echo "❌ GIS"
curl -s http://localhost:3047/health || echo "❌ ROS"
curl -s http://localhost:3010/health || echo "❌ AWD Control"
curl -s http://localhost:3011/health || echo "❌ Flow Monitoring"
curl -s http://localhost:3000/health || echo "❌ External API"

# BFF Services
echo -e "\nBFF Services:"
curl -s http://localhost:4001/health || echo "❌ Setup BFF"
curl -s http://localhost:4002/health || echo "❌ Planning BFF"
curl -s http://localhost:4003/health || echo "❌ Control BFF"
curl -s http://localhost:4004/health || echo "❌ Dashboard BFF"

# WebSockets
echo -e "\nWebSocket Services:"
curl -s http://localhost:4103/ws || echo "❌ Control WS"
curl -s http://localhost:4104/ws || echo "❌ Dashboard WS"
```

## Remember
- Each instance has specific responsibilities
- BFF services aggregate, don't duplicate logic
- Coordinate schema changes through federation
- Test integrations regularly
- Monitor performance across all instances