# Claude Instance 3: Moisture Monitoring

## Scope of Work
This instance handles soil moisture sensor data from agricultural fields, supporting multi-layer measurements for precision irrigation.

## Assigned Components

### 1. **Moisture Data Ingestion**
- **Path**: `/services/sensor-data/src/routes/moisture.routes.ts`
- **Port**: 3003 (shared with sensor-data service)
- **Queue**: `munbon-moisture-queue`
- **Responsibilities**:
  - Receive multi-depth moisture readings
  - Validate sensor data quality
  - Handle different sensor protocols
  - Process batch uploads from mobile sensors

### 2. **Moisture Monitoring Service**
- **Path**: `/services/moisture-monitoring`
- **Port**: 3005
- **Responsibilities**:
  - Soil moisture analysis by depth
  - Field-level aggregations
  - Irrigation need detection
  - Crop water stress identification
  - Moisture trend predictions

### 3. **Consumer for Moisture Queue**
- **Path**: `/services/sensor-data/src/cmd/consumer`
- **Component**: Moisture queue processor
- **Responsibilities**:
  - Poll SQS for moisture messages
  - Process multi-layer data
  - Aggregate by field/parcel
  - Quality control checks

## Environment Setup

```bash
# Moisture monitoring service
cat > services/moisture-monitoring/.env.local << EOF
SERVICE_NAME=moisture-monitoring
PORT=3005
NODE_ENV=development

# TimescaleDB for sensor data
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DB=munbon_sensors
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres123

# Sensor Configuration
SENSOR_DEPTHS=10,30,60,100  # cm
READING_INTERVAL_MS=3600000  # 1 hour
CALIBRATION_TYPE=volumetric  # volumetric or gravimetric

# Moisture Thresholds (%)
FIELD_CAPACITY=35
PERMANENT_WILTING_POINT=15
SATURATION_POINT=50
IRRIGATION_TRIGGER=25

# Soil Types
DEFAULT_SOIL_TYPE=clay_loam
SOIL_TYPES=sand,sandy_loam,loam,clay_loam,clay

# Queue Configuration
SQS_MOISTURE_QUEUE_URL=https://sqs.ap-southeast-1.amazonaws.com/123456789/munbon-moisture-queue
BATCH_SIZE=200
PROCESSING_INTERVAL_MS=10000

# Redis Cache
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=5
CACHE_TTL_SECONDS=3600

# Integration Points
GIS_SERVICE_URL=http://localhost:3007
ROS_SERVICE_URL=http://localhost:3047
CROP_SERVICE_URL=http://localhost:3012
EOF
```

## Data Schema

### Moisture Data Structure
```typescript
interface MoistureData {
  sensorId: string;
  fieldId: string;
  parcelId: string;
  timestamp: Date;
  location: {
    lat: number;
    lng: number;
  };
  measurements: Array<{
    depth: number;  // cm
    moisture: number;  // percentage
    temperature: number;  // soil temp
    ec?: number;  // electrical conductivity
  }>;
  soilType?: string;
  cropType?: string;
  batteryLevel?: number;
  sensorType: 'capacitive' | 'resistive' | 'tdr' | 'neutron';
}
```

### TimescaleDB Schema
```sql
-- Moisture measurements table
CREATE TABLE moisture_measurements (
    time TIMESTAMPTZ NOT NULL,
    sensor_id VARCHAR(50) NOT NULL,
    field_id VARCHAR(50),
    parcel_id VARCHAR(50),
    depth_cm INTEGER NOT NULL,
    moisture_percent REAL NOT NULL,
    soil_temperature REAL,
    ec_value REAL,
    soil_type VARCHAR(30),
    crop_type VARCHAR(50),
    location GEOGRAPHY(POINT, 4326),
    sensor_type VARCHAR(20),
    quality_flag VARCHAR(10)
);

-- Create hypertable
SELECT create_hypertable('moisture_measurements', 'time');

-- Indexes
CREATE INDEX idx_moisture_sensor ON moisture_measurements (sensor_id, depth_cm, time DESC);
CREATE INDEX idx_moisture_field ON moisture_measurements (field_id, time DESC);
CREATE INDEX idx_moisture_parcel ON moisture_measurements (parcel_id, time DESC);
CREATE INDEX idx_moisture_location ON moisture_measurements USING GIST(location);

-- Hourly aggregates by field
CREATE MATERIALIZED VIEW moisture_hourly_by_field
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', time) AS hour,
    field_id,
    depth_cm,
    AVG(moisture_percent) as avg_moisture,
    MIN(moisture_percent) as min_moisture,
    MAX(moisture_percent) as max_moisture,
    STDDEV(moisture_percent) as moisture_stddev,
    COUNT(*) as reading_count
FROM moisture_measurements
GROUP BY hour, field_id, depth_cm;

-- Field moisture status view
CREATE VIEW field_moisture_status AS
SELECT 
    field_id,
    AVG(CASE WHEN depth_cm = 10 THEN moisture_percent END) as surface_moisture,
    AVG(CASE WHEN depth_cm = 30 THEN moisture_percent END) as root_zone_moisture,
    AVG(CASE WHEN depth_cm = 60 THEN moisture_percent END) as deep_moisture,
    MAX(time) as last_reading
FROM moisture_measurements
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY field_id;
```

## Current Status
- ✅ Basic moisture data structure
- ✅ Multi-layer support defined
- ✅ SQS queue configuration
- ⚠️ Field aggregation: Basic only
- ❌ Irrigation detection: Not implemented
- ❌ Soil type calibration: Not implemented
- ❌ Crop-specific thresholds: Not implemented

## Priority Tasks
1. Implement soil-type specific calibrations
2. Create irrigation need detection algorithm
3. Build field-level moisture maps
4. Implement root zone moisture tracking
5. Create water stress indicators
6. Build predictive moisture models
7. Add sensor drift correction
8. Implement mobile sensor data handling

## API Endpoints

### Moisture Data
```
# Current moisture
GET /api/v1/moisture/current
GET /api/v1/moisture/field/{fieldId}/current
GET /api/v1/moisture/parcel/{parcelId}/status

# Layer analysis
GET /api/v1/moisture/field/{fieldId}/profile
GET /api/v1/moisture/depth/{depth}/map

# Historical data
GET /api/v1/moisture/history?start={date}&end={date}
GET /api/v1/moisture/field/{fieldId}/trend?days=7

# Irrigation recommendations
GET /api/v1/moisture/irrigation/needed
GET /api/v1/moisture/field/{fieldId}/irrigation-status
POST /api/v1/moisture/irrigation/calculate

# Analytics
GET /api/v1/moisture/statistics/by-zone
GET /api/v1/moisture/water-stress/fields
```

## Testing Commands

```bash
# Test moisture data ingestion
curl -X POST http://localhost:3003/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "deviceId": "MOIST-001",
    "type": "moisture",
    "data": {
      "fieldId": "F-101",
      "parcelId": "P-12345",
      "measurements": [
        {"depth": 10, "moisture": 28.5, "temperature": 25.2},
        {"depth": 30, "moisture": 32.1, "temperature": 24.8},
        {"depth": 60, "moisture": 35.5, "temperature": 24.5}
      ],
      "soilType": "clay_loam",
      "cropType": "rice"
    }
  }'

# Get field moisture profile
curl http://localhost:3005/api/v1/moisture/field/F-101/profile

# Check irrigation needs
curl http://localhost:3005/api/v1/moisture/irrigation/needed?threshold=25

# Get moisture trends
curl http://localhost:3005/api/v1/moisture/field/F-101/trend?days=7
```

## Irrigation Decision Logic

```javascript
// Multi-layer irrigation decision
function assessIrrigationNeed(moistureProfile, cropType, growthStage) {
  const rootZoneDepth = getCropRootZone(cropType, growthStage);
  const weights = getDepthWeights(rootZoneDepth);
  
  // Weighted average of root zone
  const weightedMoisture = moistureProfile.reduce((sum, layer) => {
    if (layer.depth <= rootZoneDepth) {
      return sum + (layer.moisture * weights[layer.depth]);
    }
    return sum;
  }, 0);
  
  const threshold = getIrrigationThreshold(cropType, growthStage);
  
  return {
    needsIrrigation: weightedMoisture < threshold,
    deficit: Math.max(0, threshold - weightedMoisture),
    urgency: calculateUrgency(weightedMoisture, threshold)
  };
}
```

## Soil Calibration

```javascript
// Soil-specific calibration curves
const soilCalibration = {
  sand: {
    fieldCapacity: 12,
    wiltingPoint: 4,
    saturation: 35
  },
  clay_loam: {
    fieldCapacity: 35,
    wiltingPoint: 15,
    saturation: 50
  },
  clay: {
    fieldCapacity: 40,
    wiltingPoint: 20,
    saturation: 55
  }
};

// Convert raw sensor reading to volumetric
function calibrateMoisture(rawValue, soilType, sensorType) {
  const calibration = soilCalibration[soilType];
  // Apply sensor-specific calibration curve
  return applySensorCalibration(rawValue, sensorType, calibration);
}
```

## Integration Points

### With ROS Service (Instance 6)
```javascript
// Provide moisture data for water demand calculation
export async function getFieldMoistureForROS(fieldId) {
  const moisture = await getFieldMoistureProfile(fieldId);
  return {
    rootZoneMoisture: moisture.avgRootZone,
    deficit: calculateDeficit(moisture),
    lastUpdated: moisture.timestamp
  };
}
```

### With GIS Service (Instance 4)
```javascript
// Generate moisture maps
export async function generateMoistureMap(zoneId, depth) {
  const parcels = await gisService.getParcelsInZone(zoneId);
  const moistureData = await getMoistureByParcels(parcels, depth);
  return createGeoJSON(parcels, moistureData);
}
```

## Mobile Sensor Handling

```javascript
// Handle batch upload from mobile app
async function processMobileSensorData(batch) {
  // Validate GPS coordinates
  // Check timestamp freshness
  // Apply movement correction
  // Group by field
  // Store with mobile flag
}
```

## Notes for Development
- Account for sensor placement variations
- Handle seasonal soil property changes
- Implement temperature compensation
- Support different measurement units
- Consider rainfall effects on readings
- Add manual measurement capability
- Handle sensor maintenance periods
- Support offline data collection