# Claude Instance 1: Data Ingestion

## Scope of Work
This instance handles all real-time sensor data ingestion from IoT devices.

## Assigned Services

### 1. **Sensor Data Service** (Primary)
- **Path**: `/services/sensor-data`
- **Port**: 3003
- **Responsibilities**:
  - MQTT broker connection for IoT data
  - AWS SQS message processing
  - Data validation and transformation
  - Write to TimescaleDB
  - Real-time data streaming

### 2. **Consumer/Queue Processor**
- **Path**: `/services/sensor-data/src/cmd/consumer`
- **Port**: 3004 (Dashboard)
- **Responsibilities**:
  - Poll SQS queues
  - Process messages in batches
  - Handle retries and DLQ
  - Monitoring dashboard

### 3. **Water Level Monitoring** (Analytics)
- **Path**: `/services/water-level-monitoring`
- **Port**: 3008
- **Responsibilities**:
  - Read from TimescaleDB
  - Calculate trends and predictions
  - Flood/drought alerts
  - Gate control recommendations

### 4. **Moisture Monitoring** (Analytics)
- **Path**: `/services/moisture-monitoring`
- **Port**: 3005
- **Responsibilities**:
  - Multi-layer soil analysis
  - Irrigation recommendations
  - Field aggregations
  - Drought detection

## Environment Setup

```bash
# Copy this to start your instance
cd /Users/subhajlimanond/dev/munbon2-backend

# Set up environment files
cp services/sensor-data/.env.local.example services/sensor-data/.env.local
cp services/water-level-monitoring/.env.local.example services/water-level-monitoring/.env.local
cp services/moisture-monitoring/.env.local.example services/moisture-monitoring/.env.local
```

## Key Configurations

### TimescaleDB Connection
```env
# services/sensor-data/.env.local
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DB=munbon_sensors
```

### SQS Queues
```env
# Sensor data queues
WATER_LEVEL_QUEUE=munbon-water-level-queue
MOISTURE_QUEUE=munbon-moisture-queue
WEATHER_QUEUE=munbon-weather-queue
```

### MQTT Topics
```env
MQTT_BROKER=mqtt://localhost:1883
MQTT_TOPICS=sensors/+/water-level,sensors/+/moisture,sensors/+/weather
```

## Data Flow
```
IoT Sensors → MQTT/HTTP → Sensor Data Service → SQS → Consumer → TimescaleDB
                                                             ↓
                                    Analytics Services (Water/Moisture Monitoring)
```

## Current Status
- ✅ Sensor Data Service: Implemented
- ✅ SQS Integration: Working
- ✅ Consumer: Functional
- ⚠️ Water Level Monitoring: Basic implementation
- ⚠️ Moisture Monitoring: Basic implementation

## Priority Tasks
1. Optimize batch processing for high-volume data
2. Implement data retention policies
3. Add real-time WebSocket streaming
4. Create aggregation tables for faster queries
5. Implement alert thresholds

## Testing Commands
```bash
# Test sensor data ingestion
curl -X POST http://localhost:3003/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{"deviceId":"sensor-001","type":"water-level","value":2.5}'

# Check consumer status
curl http://localhost:3004/stats

# Test water level analytics
curl http://localhost:3008/api/v1/analysis/trends?hours=24
```

## Key Files to Focus On
- `/services/sensor-data/src/routes/telemetry.routes.ts`
- `/services/sensor-data/src/services/sqs-processor.ts`
- `/services/sensor-data/src/cmd/consumer/main.ts`
- `/services/water-level-monitoring/src/services/analysis.service.ts`
- `/services/moisture-monitoring/src/services/alert.service.ts`

## Dependencies
- TimescaleDB must be running
- Redis for caching
- AWS credentials for SQS
- MQTT broker (optional)

## Notes for Development
- Use batch inserts for performance
- Implement circuit breakers for external services
- Add comprehensive logging for debugging
- Monitor queue depths to prevent backlogs
- Use time-based partitioning in TimescaleDB