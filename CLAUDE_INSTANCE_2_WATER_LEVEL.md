# Claude Instance 2: Water Level Monitoring

## Scope of Work
This instance handles water level sensor data from canals, reservoirs, and monitoring stations throughout the irrigation system.

## Assigned Components

### 1. **Water Level Data Ingestion**
- **Path**: `/services/sensor-data/src/routes/water-level.routes.ts`
- **Port**: 3003 (shared with sensor-data service)
- **Queue**: `munbon-water-level-queue`
- **Responsibilities**:
  - Receive ultrasonic/pressure sensor data
  - Validate water level readings
  - Handle multiple sensor types
  - Real-time data streaming

### 2. **Water Level Monitoring Service**
- **Path**: `/services/water-level-monitoring`
- **Port**: 3008
- **Responsibilities**:
  - Water level trend analysis
  - Flow rate calculations
  - Flood/drought warnings
  - Gate control recommendations
  - Reservoir capacity monitoring

### 3. **Consumer for Water Level Queue**
- **Path**: `/services/sensor-data/src/cmd/consumer`
- **Component**: Water level queue processor
- **Responsibilities**:
  - Poll SQS for water level messages
  - Batch process sensor readings
  - Store in TimescaleDB
  - Handle sensor anomalies

## Environment Setup

```bash
# Water level monitoring service
cat > services/water-level-monitoring/.env.local << EOF
SERVICE_NAME=water-level-monitoring
PORT=3008
NODE_ENV=development

# TimescaleDB for sensor data
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DB=munbon_sensors
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres123

# Sensor Configuration
SENSOR_TYPES=ultrasonic,pressure,radar,float
READING_INTERVAL_MS=60000  # 1 minute
ANOMALY_THRESHOLD=0.5  # meters sudden change

# Alert Thresholds (meters above datum)
FLOOD_WARNING_LEVEL=4.5
FLOOD_DANGER_LEVEL=5.0
DROUGHT_WARNING_LEVEL=1.0
DROUGHT_CRITICAL_LEVEL=0.5

# Flow Calculation
CANAL_WIDTH_DEFAULT=10  # meters
MANNING_COEFFICIENT=0.035  # concrete canal

# Queue Configuration
SQS_WATER_LEVEL_QUEUE_URL=https://sqs.ap-southeast-1.amazonaws.com/123456789/munbon-water-level-queue
BATCH_SIZE=100
PROCESSING_INTERVAL_MS=5000

# Redis Cache
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=8
CACHE_TTL_SECONDS=60

# Integration Points
GIS_SERVICE_URL=http://localhost:3007
WATER_CONTROL_SERVICE_URL=http://localhost:3011
EOF
```

## Data Schema

### Water Level Data Structure
```typescript
interface WaterLevelData {
  sensorId: string;
  location: {
    lat: number;
    lng: number;
    canalId?: string;
    reservoirId?: string;
    gateId?: string;
  };
  timestamp: Date;
  waterLevel: {
    current: number;  // meters
    reference: 'MSL' | 'LOCAL_DATUM' | 'SENSOR_ZERO';
    quality: 'GOOD' | 'SUSPECT' | 'BAD';
  };
  sensorType: 'ultrasonic' | 'pressure' | 'radar' | 'float';
  batteryLevel?: number;
  signalStrength?: number;
  temperature?: number;  // Water temperature
}
```

### TimescaleDB Schema
```sql
-- Water level measurements
CREATE TABLE water_level_measurements (
    time TIMESTAMPTZ NOT NULL,
    sensor_id VARCHAR(50) NOT NULL,
    water_level REAL NOT NULL,
    reference_type VARCHAR(20),
    quality_flag VARCHAR(10),
    sensor_type VARCHAR(20),
    canal_id VARCHAR(50),
    reservoir_id VARCHAR(50),
    gate_id VARCHAR(50),
    location GEOGRAPHY(POINT, 4326),
    battery_level REAL,
    signal_strength INTEGER,
    water_temperature REAL
);

-- Create hypertable
SELECT create_hypertable('water_level_measurements', 'time');

-- Indexes
CREATE INDEX idx_water_sensor ON water_level_measurements (sensor_id, time DESC);
CREATE INDEX idx_water_location ON water_level_measurements USING GIST(location);
CREATE INDEX idx_water_canal ON water_level_measurements (canal_id, time DESC);

-- 5-minute aggregates
CREATE MATERIALIZED VIEW water_level_5min
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('5 minutes', time) AS bucket,
    sensor_id,
    AVG(water_level) as avg_level,
    MAX(water_level) as max_level,
    MIN(water_level) as min_level,
    COUNT(*) as reading_count
FROM water_level_measurements
GROUP BY bucket, sensor_id;

-- Flow rate calculations view
CREATE VIEW flow_rates AS
SELECT 
    w.time,
    w.canal_id,
    w.water_level,
    -- Simple flow calculation (needs canal dimensions)
    w.water_level * 10 * 1.5 as flow_rate_cms  -- Simplified
FROM water_level_measurements w
WHERE w.canal_id IS NOT NULL;
```

## Current Status
- ✅ Basic water level data structure
- ✅ SQS queue configuration
- ✅ Consumer framework exists
- ⚠️ Sensor data validation: Basic only
- ❌ Flow rate calculations: Not implemented
- ❌ Trend analysis: Not implemented
- ❌ Alert system: Not implemented

## Priority Tasks
1. Implement robust data validation with sensor-specific rules
2. Create flow rate calculation engine
3. Build water level trend analysis
4. Implement flood/drought prediction algorithms
5. Create real-time alerting system
6. Build gate control recommendation engine
7. Add sensor health monitoring
8. Implement data gap interpolation

## API Endpoints

### Water Level Data
```
# Current levels
GET /api/v1/water-level/current
GET /api/v1/water-level/sensor/{sensorId}/current
GET /api/v1/water-level/canal/{canalId}/current

# Historical data
GET /api/v1/water-level/history?start={datetime}&end={datetime}
GET /api/v1/water-level/sensor/{sensorId}/trend?hours=24

# Analytics
GET /api/v1/water-level/statistics?period=daily
GET /api/v1/water-level/flow-rate/canal/{canalId}
GET /api/v1/water-level/predictions?hours=6

# Alerts
GET /api/v1/water-level/alerts/active
POST /api/v1/water-level/alerts/thresholds
```

## Testing Commands

```bash
# Test water level data ingestion
curl -X POST http://localhost:3003/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "deviceId": "WL-SENSOR-001",
    "type": "water-level",
    "data": {
      "waterLevel": 2.45,
      "reference": "LOCAL_DATUM",
      "sensorType": "ultrasonic",
      "location": {
        "lat": 14.88,
        "lng": 102.02,
        "canalId": "C-001"
      }
    }
  }'

# Get current water levels
curl http://localhost:3008/api/v1/water-level/current

# Get canal flow rate
curl http://localhost:3008/api/v1/water-level/flow-rate/canal/C-001

# Check flood alerts
curl http://localhost:3008/api/v1/water-level/alerts/active?type=flood
```

## Flow Rate Calculations

```javascript
// Manning's equation for open channel flow
function calculateFlowRate(waterLevel, canalWidth, slope, manningN) {
  const area = waterLevel * canalWidth;
  const perimeter = canalWidth + 2 * waterLevel;
  const hydraulicRadius = area / perimeter;
  const velocity = (1/manningN) * Math.pow(hydraulicRadius, 2/3) * Math.sqrt(slope);
  return area * velocity; // m³/s
}
```

## Alert Logic

```javascript
// Flood detection
if (currentLevel > FLOOD_WARNING_LEVEL) {
  if (rateOfRise > 0.1) { // 10cm/hour
    createAlert('FLOOD_WARNING', 'Rapid water level rise detected');
  }
}

// Drought detection
if (currentLevel < DROUGHT_WARNING_LEVEL) {
  if (trend.days7 < 0) { // Declining for 7 days
    createAlert('DROUGHT_WARNING', 'Sustained low water levels');
  }
}
```

## Integration Points

### With Water Control Service
```javascript
// Recommend gate operations based on levels
async function recommendGateOperation(canalId) {
  const levels = await getWaterLevels(canalId);
  if (levels.upstream > levels.downstream + 0.5) {
    return { action: 'OPEN', percentage: 25 };
  }
}
```

### With GIS Service (Instance 4)
```javascript
// Get canal geometry for flow calculations
const canalGeometry = await gisService.getCanalDimensions(canalId);
const flowRate = calculateFlowRate(waterLevel, canalGeometry);
```

## Sensor Health Monitoring
- Check battery levels < 20%
- Detect stuck sensors (no change > 24h)
- Flag readings outside physical limits
- Monitor communication gaps
- Track sensor drift over time

## Notes for Development
- Handle sensor calibration offsets
- Account for tidal effects if applicable
- Implement sensor redundancy checks
- Consider seasonal variations
- Add manual reading override capability
- Support mobile sensor deployments
- Handle network outages gracefully