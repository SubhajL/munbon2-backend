# Flow Monitoring Service - End-to-End Architecture

## Service Overview
**Port**: 3011 (localhost:3011)  
**Technology**: Python/FastAPI  
**Purpose**: Real-time flow monitoring, hydraulic calculations, and irrigation scheduling

## Complete Data Flow (Frontend → Backend → Hardware)

### 1. User Initiates Irrigation Request (Frontend)

```
Frontend (React/Vue)
    │
    ├─[1]─> User selects zones and volumes
    │       - Zone 2: 10,000 m³
    │       - Zone 5: 7,500 m³
    │       - Zone 6: 5,000 m³
    │
    └─[2]─> POST to BFF Service
            http://localhost:3020/api/irrigation/schedule
```

### 2. BFF Service (Backend for Frontend)

```
BFF Service (Port 3020)
    │
    ├─[3]─> Aggregates user request
    │
    ├─[4]─> Calls Flow Monitoring Service
    │       POST http://localhost:3011/api/v1/irrigation/schedule
    │       {
    │         "requests": [
    │           {"zone": "Zone 2", "volume_m3": 10000, "flow_rate_m3s": 2.0},
    │           {"zone": "Zone 5", "volume_m3": 7500, "flow_rate_m3s": 1.5},
    │           {"zone": "Zone 6", "volume_m3": 5000, "flow_rate_m3s": 1.0}
    │         ],
    │         "start_time": "2024-01-15T08:00:00Z"
    │       }
    │
    └─[5]─> Also queries current system state
            GET http://localhost:3011/api/v1/network/status
```

### 3. Flow Monitoring Service API Endpoints

```
Flow Monitoring Service (Port 3011)
│
├── /api/v1/irrigation
│   ├── POST   /schedule         # Create irrigation schedule
│   ├── GET    /schedule/{id}    # Get schedule details
│   ├── PUT    /schedule/{id}    # Update schedule
│   └── DELETE /schedule/{id}    # Cancel schedule
│
├── /api/v1/network
│   ├── GET    /status           # Current water levels & flows
│   ├── GET    /topology         # Network structure
│   └── GET    /gates            # Gate positions & status
│
├── /api/v1/hydraulics
│   ├── POST   /solve            # Run hydraulic solver
│   ├── POST   /simulate         # Run time simulation
│   └── GET    /convergence      # Get solver status
│
├── /api/v1/telemetry
│   ├── POST   /flow             # Ingest flow data
│   ├── POST   /level            # Ingest level data
│   ├── GET    /flow/history     # Historical flow data
│   └── GET    /level/history    # Historical level data
│
├── /api/v1/analysis
│   ├── GET    /water-balance    # Water balance calculations
│   ├── GET    /losses           # Loss detection
│   └── GET    /efficiency       # System efficiency metrics
│
└── /metrics                     # Prometheus metrics
```

### 4. Internal Processing Flow

```
Flow Monitoring Service Internal Flow:

[6] Receive Schedule Request
    │
    ├─[7]─> Path Calculator
    │       - Find paths: Source → Zone 2/5/6
    │       - Identify shared segments
    │
    ├─[8]─> Hydraulic Solver (Iterative)
    │       - Initial water levels
    │       - Calculate gate flows
    │       - Update levels based on continuity
    │       - Iterate until convergence
    │
    ├─[9]─> Travel Time Calculator
    │       - Use canal geometry data
    │       - Calculate water velocity
    │       - Determine arrival times
    │
    ├─[10]→ Gate Optimizer
    │       - Calculate required openings
    │       - Handle capacity constraints
    │       - Optimize for efficiency
    │
    └─[11]→ Schedule Generator
            - Gate opening sequence
            - Precise timing
            - Flow reduction schedule
```

### 5. Data Storage

```
Databases:
    │
    ├── TimescaleDB (Port 5433)
    │   └── Time-series data
    │       - flow_measurements
    │       - level_measurements
    │       - gate_positions
    │
    ├── InfluxDB (Port 8086)
    │   └── High-frequency sensor data
    │       - real_time_flow
    │       - real_time_levels
    │
    └── PostgreSQL (Port 5432)
        └── Configuration & state
            - canal_geometry
            - gate_properties
            - irrigation_schedules
```

### 6. External Communications

```
[12] SCADA Integration
     │
     ├─→ Publish to Kafka
     │   Topic: gate-commands
     │   {
     │     "gate_id": "Source->M(0,0)",
     │     "command": "open",
     │     "position": 90.0,
     │     "timestamp": "2024-01-15T04:54:00Z"
     │   }
     │
     └─→ SCADA Service (Port 3005)
         └─→ OPC UA → GE iFix → Physical Gates
```

### 7. Real-time Monitoring

```
[13] Sensor Data Ingestion
     │
     ├─← MQTT Broker
     │   - Flow sensors
     │   - Level sensors
     │   - Gate position feedback
     │
     └─← Kafka Topics
         - sensor-data-flow
         - sensor-data-level
         - gate-status
```

### 8. Response to Frontend

```
[14] Response Flow
     │
     ├─→ Flow Monitoring → BFF
     │   {
     │     "schedule_id": "SCH-2024-0115-001",
     │     "status": "scheduled",
     │     "gate_operations": [
     │       {
     │         "gate_id": "Source->M(0,0)",
     │         "action": "open",
     │         "time": "2024-01-15T04:54:00Z",
     │         "opening_percent": 90.0
     │       },
     │       // ... more operations
     │     ],
     │     "timeline": {
     │       "Zone 2": {
     │         "water_arrival": "2024-01-15T08:00:00Z",
     │         "completion": "2024-01-15T09:23:00Z"
     │       }
     │       // ... other zones
     │     }
     │   }
     │
     └─→ BFF → Frontend
         - Formatted for UI display
         - WebSocket updates for real-time status
```

## API Examples

### 1. Create Irrigation Schedule
```bash
curl -X POST http://localhost:3011/api/v1/irrigation/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "requests": [
      {
        "zone": "Zone 2",
        "volume_m3": 10000,
        "flow_rate_m3s": 2.0,
        "priority": 1
      }
    ],
    "start_time": "2024-01-15T08:00:00Z"
  }'
```

### 2. Get Current Network Status
```bash
curl http://localhost:3011/api/v1/network/status

Response:
{
  "timestamp": "2024-01-15T07:30:00Z",
  "water_levels": {
    "Source": 221.0,
    "M(0,0)": 219.2,
    "M(0,2)": 218.7,
    // ...
  },
  "flows": {
    "Source->M(0,0)": 4.5,
    "M(0,0)->M(0,2)": 4.5,
    // ...
  },
  "gate_positions": {
    "Source->M(0,0)": 90.0,
    "M(0,0)->M(0,2)": 90.0,
    // ...
  }
}
```

### 3. Run Hydraulic Simulation
```bash
curl -X POST http://localhost:3011/api/v1/hydraulics/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "gate_settings": [
      {"upstream": "Source", "downstream": "M(0,0)", "opening": 2.5}
    ],
    "duration_hours": 4,
    "time_step_seconds": 60
  }'
```

### 4. Get Historical Flow Data
```bash
curl "http://localhost:3011/api/v1/telemetry/flow/history?\
gate_id=Source->M(0,0)&\
start_time=2024-01-15T00:00:00Z&\
end_time=2024-01-15T23:59:59Z"
```

## WebSocket Real-time Updates

```javascript
// Frontend WebSocket connection
const ws = new WebSocket('ws://localhost:3011/ws');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  
  switch(update.type) {
    case 'water_level':
      // Update level display
      updateWaterLevel(update.node, update.level);
      break;
      
    case 'gate_position':
      // Update gate visualization
      updateGatePosition(update.gate_id, update.position);
      break;
      
    case 'flow_rate':
      // Update flow animation
      updateFlowRate(update.gate_id, update.flow);
      break;
  }
};
```

## Error Handling

```json
// Error Response Format
{
  "error": {
    "code": "HYDRAULIC_CONVERGENCE_FAILED",
    "message": "Hydraulic solver failed to converge after 50 iterations",
    "details": {
      "max_residual": 0.15,
      "problem_nodes": ["M(0,3)", "M(0,5)"],
      "suggested_action": "Check gate capacity constraints"
    }
  },
  "timestamp": "2024-01-15T07:45:23Z"
}
```

## Health Check Endpoint

```bash
curl http://localhost:3011/health

Response:
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "database_connections": {
    "timescaledb": "connected",
    "influxdb": "connected",
    "postgresql": "connected"
  },
  "kafka_consumer": "running",
  "last_telemetry_received": "2024-01-15T07:59:45Z"
}
```

## Security Headers

All endpoints include:
- `Authorization: Bearer {JWT_TOKEN}`
- `X-Request-ID: {UUID}`
- `X-User-ID: {USER_ID}`

## Rate Limiting

- General API: 100 requests/minute
- Telemetry ingestion: 1000 requests/minute
- WebSocket connections: 10 per user

This complete E2E architecture ensures reliable water delivery with real-time monitoring and control!