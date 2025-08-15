# AWD Control Service - Inputs & Outputs Reference

## 1. REQUIRED INPUTS

### 1.1 Field Registration & Configuration

| Input | Type | How to Provide | Required Fields |
|-------|------|----------------|-----------------|
| **Field Registration** | JSON | POST `/api/v1/awd/fields` | - field_code (string)<br>- field_name (string)<br>- zone_id (integer)<br>- area_hectares (decimal)<br>- soil_type (string)<br>- awd_enabled (boolean) |
| **AWD Configuration** | JSON | POST `/api/v1/awd/fields/:fieldId/config` | - planting_method ('transplanted' or 'direct-seeded')<br>- start_date (timestamp)<br>- drying_depth_cm (default: 15)<br>- safe_awd_depth_cm (default: 10)<br>- emergency_threshold_cm (default: 25) |

**Example Field Registration:**
```bash
curl -X POST http://localhost:3013/api/v1/awd/fields \
  -H "Content-Type: application/json" \
  -d '{
    "field_code": "F001-Z3",
    "field_name": "North Field Block A",
    "zone_id": 3,
    "area_hectares": 2.5,
    "soil_type": "clay",
    "awd_enabled": true
  }'
```

### 1.2 Sensor Registration

| Input | Type | How to Provide | Required Fields |
|-------|------|----------------|-----------------|
| **AWD Sensor** | JSON | POST `/api/v1/awd/sensors` | - sensor_id (string)<br>- field_id (UUID)<br>- sensor_type ('water_level' or 'moisture')<br>- mac_address (optional)<br>- calibration_offset (default: 0) |

**Example Sensor Registration:**
```bash
curl -X POST http://localhost:3013/api/v1/awd/sensors \
  -H "Content-Type: application/json" \
  -d '{
    "sensor_id": "AWD-B7E6",
    "field_id": "123e4567-e89b-12d3-a456-426614174000",
    "sensor_type": "water_level",
    "mac_address": "B7:E6:AA:BB:CC:DD"
  }'
```

### 1.3 Real-Time Sensor Data

| Input | Type | How to Provide | Data Format |
|-------|------|----------------|-------------|
| **Water Level Data** | Kafka Message | Topic: `awd.sensor.data` | - time (timestamp)<br>- sensor_id (string)<br>- field_id (UUID)<br>- water_level_cm (decimal)<br>- temperature_celsius (decimal)<br>- battery_voltage (decimal) |
| **Moisture Data** | Kafka Message | Topic: `awd.sensor.data` | - time (timestamp)<br>- sensor_id (string)<br>- field_id (UUID)<br>- moisture_percent (decimal)<br>- depth_cm (decimal)<br>- temperature_celsius (decimal) |

**Kafka Message Format:**
```json
{
  "type": "water_level",
  "time": "2025-01-20T10:30:00Z",
  "sensor_id": "AWD-B7E6",
  "field_id": "123e4567-e89b-12d3-a456-426614174000",
  "water_level_cm": -12.5,
  "temperature_celsius": 28.3,
  "battery_voltage": 3.7
}
```

### 1.4 Manual Control Inputs

| Input | Type | How to Provide | Parameters |
|-------|------|----------------|------------|
| **Manual Irrigation** | JSON | POST `/api/v1/awd/fields/:fieldId/control` | - action ('start_irrigation' or 'stop_irrigation')<br>- duration_minutes (if starting)<br>- reason (string) |
| **Override AWD** | JSON | PUT `/api/v1/awd/fields/:fieldId/control` | - override_enabled (boolean)<br>- override_reason (string)<br>- override_until (timestamp) |

### 1.5 External Service Inputs

| Input | Type | Source Service | Data Retrieved |
|-------|------|----------------|----------------|
| **Weather Data** | API Call | Weather Service (3006) | - rainfall_mm<br>- rainfall_forecast<br>- evapotranspiration<br>- temperature |
| **GIS Water Level** | Database | PostgreSQL (gis schema) | - plot_id<br>- water_height_cm<br>- measurement_date<br>- geometry |

## 2. COMPUTED OUTPUTS

### 2.1 AWD Status & Recommendations

| Output | Type | Computation | Where to Get |
|--------|------|-------------|--------------|
| **Current AWD Status** | JSON | Real-time calculation | GET `/api/v1/awd/fields/:fieldId/status` |
| **Irrigation Recommendation** | JSON | AWD algorithm | GET `/api/v1/awd/recommendations?field_id=:fieldId` |
| **Next Irrigation Time** | Timestamp | Based on drying rate | In status response: `next_irrigation_date` |
| **Current Phase** | String | Week-based lookup | In status response: `current_phase` |

**API Response Example:**
```json
{
  "field_id": "123e4567-e89b-12d3-a456-426614174000",
  "current_water_level_cm": -12.5,
  "current_phase": "early_drying",
  "days_since_drying": 3,
  "irrigation_needed": false,
  "next_irrigation_date": "2025-01-23T08:00:00Z",
  "water_stress_risk": "low",
  "recommendation": "Continue drying for 2 more days"
}
```

### 2.2 Water Savings Analytics

| Output | Type | Computation | Where to Get |
|--------|------|-------------|--------------|
| **Water Saved (L)** | Decimal | Baseline - Actual usage | GET `/api/v1/awd/analytics/water-savings?field_id=:fieldId` |
| **Savings Percentage** | Decimal | (Saved/Baseline) × 100 | In analytics response |
| **Cumulative Savings** | Decimal | Sum of all cycles | Database: `SELECT SUM(water_saved_liters) FROM awd.irrigation_events WHERE field_id = ?` |

**Database Query for Water Savings:**
```sql
-- Get water savings for a field
SELECT 
    fc.field_id,
    COUNT(DISTINCT fc.id) as total_cycles,
    SUM(ie.water_volume_liters) as total_water_used,
    SUM(ie.water_saved_liters) as total_water_saved,
    AVG(ie.water_saved_percent) as avg_savings_percent
FROM awd.awd_field_cycles fc
JOIN sensor_data.irrigation_events ie ON fc.field_id = ie.field_id
WHERE fc.field_id = '123e4567-e89b-12d3-a456-426614174000'
    AND fc.cycle_status = 'completed'
GROUP BY fc.field_id;
```

### 2.3 Irrigation Events & History

| Output | Type | Where to Get | Data Included |
|--------|------|--------------|---------------|
| **Irrigation History** | JSON Array | GET `/api/v1/awd/fields/:fieldId/history` | - irrigation start/end times<br>- water volume used<br>- water level before/after |
| **Active Irrigations** | JSON Array | Redis: `irrigation:active:*` | - field_id<br>- start_time<br>- expected_end_time |
| **Scheduled Irrigations** | Table Records | `awd.irrigation_schedules WHERE status = 'pending'` | - scheduled_start<br>- duration<br>- priority |

### 2.4 Sensor Performance Metrics

| Output | Type | Computation | Where to Get |
|--------|------|-------------|--------------|
| **Sensor Reliability** | Percentage | (Successful readings / Expected readings) × 100 | GET `/api/v1/awd/sensors/:sensorId/metrics` |
| **Data Gap Analysis** | Time periods | Missing data detection | Database query on TimescaleDB |
| **Battery Status** | Voltage/Percentage | Latest reading | `SELECT battery_voltage FROM sensor_data.awd_sensor_readings WHERE sensor_id = ? ORDER BY time DESC LIMIT 1` |

### 2.5 AWD Cycle Metrics

| Output | Type | Where to Get | Example Query |
|--------|------|--------------|---------------|
| **Current Cycle Info** | Database | `awd.awd_field_cycles` | `SELECT * FROM awd.awd_field_cycles WHERE field_id = ? AND cycle_status = 'active'` |
| **Cycle Duration** | Days | Calculated from dates | `SELECT EXTRACT(DAY FROM NOW() - drying_start_date) as drying_days` |
| **Average Cycle Length** | Days | Historical average | `SELECT AVG(drying_day_count) FROM awd.awd_field_cycles WHERE field_id = ?` |

## 3. OUTPUT RETRIEVAL METHODS

### 3.1 REST API Endpoints

```bash
# Get field status
GET /api/v1/awd/fields/:fieldId/status

# Get sensor readings
GET /api/v1/awd/fields/:fieldId/sensors

# Get irrigation history
GET /api/v1/awd/fields/:fieldId/history?start_date=2025-01-01&end_date=2025-01-31

# Get water savings analytics
GET /api/v1/awd/analytics/water-savings?field_id=:fieldId&period=monthly

# Get recommendations
GET /api/v1/awd/recommendations?zone_id=3
```

### 3.2 Direct Database Queries

```sql
-- Current water level from sensor
SELECT time, water_level_cm 
FROM sensor_data.awd_sensor_readings 
WHERE field_id = '123e4567-e89b-12d3-a456-426614174000'
ORDER BY time DESC 
LIMIT 1;

-- Field configuration
SELECT * FROM awd.awd_configurations 
WHERE field_id = '123e4567-e89b-12d3-a456-426614174000';

-- Irrigation events in last 7 days
SELECT * FROM sensor_data.irrigation_events 
WHERE field_id = '123e4567-e89b-12d3-a456-426614174000'
    AND time >= NOW() - INTERVAL '7 days'
ORDER BY time DESC;

-- Active sensors for a field
SELECT * FROM awd.awd_sensors 
WHERE field_id = '123e4567-e89b-12d3-a456-426614174000'
    AND status = 'active';
```

### 3.3 Redis Cache Keys

```bash
# Get current field status from cache
redis-cli GET "field:123e4567-e89b-12d3-a456-426614174000:status"

# Get latest sensor reading
redis-cli GET "sensor:AWD-B7E6:latest"

# Get irrigation queue
redis-cli LRANGE "irrigation:queue" 0 -1

# Get active irrigation
redis-cli GET "irrigation:active:123e4567-e89b-12d3-a456-426614174000"
```

### 3.4 Kafka Topics for Real-time Updates

```bash
# Subscribe to irrigation events
kafka-console-consumer --topic awd.irrigation.events --from-beginning

# Subscribe to control commands
kafka-console-consumer --topic awd.control.commands --from-beginning
```

## 4. SPECIAL OUTPUTS

### 4.1 Aggregated Metrics (Continuous Aggregates)

```sql
-- Hourly water level averages (pre-computed)
SELECT * FROM sensor_data.awd_water_level_hourly 
WHERE field_id = '123e4567-e89b-12d3-a456-426614174000'
    AND hour >= NOW() - INTERVAL '24 hours';
```

### 4.2 Alert Conditions

| Alert Type | Condition | Output Location |
|------------|-----------|-----------------|
| Critical Water Level | water_level < -emergency_threshold | Kafka: `awd.alerts` topic |
| Sensor Offline | No data > 1 hour | Redis: `alerts:sensor:offline` |
| Irrigation Failure | Scheduled but not executed | Database: `awd.irrigation_schedules` status = 'failed' |

## 5. DATA FLOW SUMMARY

```
INPUTS                          PROCESSING                      OUTPUTS
------                          ----------                      -------
Field Registration      →       Store in PostgreSQL      →      Field ID
Sensor Registration     →       Validate & Store         →      Sensor Status
Sensor Data (Kafka)     →       AWD Algorithm            →      Irrigation Decision
Weather Data (API)      →       Risk Assessment          →      Adjusted Thresholds
Manual Override         →       Update Configuration     →      New Schedule

                               ↓ Compute ↓

                        Water Savings Metrics
                        Irrigation History
                        Performance Analytics
                        Real-time Status
```