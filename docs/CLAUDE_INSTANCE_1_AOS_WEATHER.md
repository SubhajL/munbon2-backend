# Claude Instance 1: AOS Weather Data

## Scope of Work
This instance handles AOS (Automatic Observation System) weather station data ingestion, processing, and analytics.

## Assigned Components

### 1. **AOS Data Ingestion**
- **Path**: `/services/sensor-data/src/routes/aos.routes.ts`
- **Port**: 3003 (shared with sensor-data service)
- **Queue**: `munbon-aos-weather-queue`
- **Responsibilities**:
  - Fetch data from AOS weather stations
  - Parse meteorological data formats
  - Validate weather parameters
  - Store in TimescaleDB

### 2. **Weather Monitoring Service**
- **Path**: `/services/weather-monitoring`
- **Port**: 3006
- **Responsibilities**:
  - Weather trend analysis
  - Rainfall prediction
  - Temperature anomaly detection
  - ETo calculation support
  - Weather alerts

### 3. **External Weather APIs**
- **Integrations**:
  - Thai Meteorological Department (TMD)
  - AOS Weather Station Network
  - OpenWeatherMap (backup)

## Environment Setup

```bash
# Weather monitoring service
cat > services/weather-monitoring/.env.local << EOF
SERVICE_NAME=weather-monitoring
PORT=3006
NODE_ENV=development

# TimescaleDB for weather data
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DB=munbon_sensors
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres123

# AOS Configuration
AOS_API_URL=http://www.aos-weather.com/api
AOS_STATION_IDS=ST001,ST002,ST003
AOS_FETCH_INTERVAL_MS=300000  # 5 minutes

# TMD API
TMD_API_URL=https://api.tmd.go.th/v1
TMD_API_KEY=your-tmd-api-key
TMD_PROVINCE_CODE=31  # Nakhon Ratchasima

# Weather Parameters
TEMPERATURE_UNIT=celsius
WIND_SPEED_UNIT=m/s
PRESSURE_UNIT=hPa
RAINFALL_UNIT=mm

# Alert Thresholds
TEMP_HIGH_THRESHOLD=40
TEMP_LOW_THRESHOLD=10
RAINFALL_HEAVY_THRESHOLD=50
WIND_STRONG_THRESHOLD=20

# Queue Configuration
SQS_WEATHER_QUEUE_URL=https://sqs.ap-southeast-1.amazonaws.com/123456789/munbon-aos-weather-queue

# Redis Cache
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=6
CACHE_TTL_SECONDS=300
EOF
```

## Data Schema

### Weather Data Structure
```typescript
interface AOSWeatherData {
  stationId: string;
  timestamp: Date;
  temperature: {
    current: number;
    min: number;
    max: number;
  };
  humidity: number;
  pressure: number;
  windSpeed: number;
  windDirection: number;
  rainfall: {
    hourly: number;
    daily: number;
    accumulated: number;
  };
  solarRadiation: number;
  uvIndex: number;
  visibility: number;
  cloudCover: number;
}
```

### TimescaleDB Schema
```sql
-- Weather measurements table
CREATE TABLE weather_measurements (
    time TIMESTAMPTZ NOT NULL,
    station_id VARCHAR(50) NOT NULL,
    temperature REAL,
    humidity REAL,
    pressure REAL,
    wind_speed REAL,
    wind_direction INTEGER,
    rainfall REAL,
    solar_radiation REAL,
    uv_index REAL,
    visibility REAL,
    cloud_cover INTEGER,
    quality_flag INTEGER
);

-- Create hypertable
SELECT create_hypertable('weather_measurements', 'time');

-- Create indexes
CREATE INDEX idx_weather_station ON weather_measurements (station_id, time DESC);
CREATE INDEX idx_weather_params ON weather_measurements (temperature, rainfall, time DESC);

-- Continuous aggregates for hourly data
CREATE MATERIALIZED VIEW weather_hourly
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', time) AS hour,
    station_id,
    AVG(temperature) as avg_temp,
    MAX(temperature) as max_temp,
    MIN(temperature) as min_temp,
    AVG(humidity) as avg_humidity,
    SUM(rainfall) as total_rainfall,
    AVG(wind_speed) as avg_wind_speed
FROM weather_measurements
GROUP BY hour, station_id;
```

## Current Status
- ✅ Basic weather data structure defined
- ✅ SQS queue created
- ⚠️ AOS API integration: Partial
- ⚠️ TMD API integration: Credentials needed
- ❌ Weather monitoring service: Not implemented
- ❌ ETo calculation integration: Not connected
- ❌ Weather alerts: Not implemented

## Priority Tasks
1. Implement AOS API data fetcher
2. Create weather data parser for multiple formats
3. Set up scheduled data collection (cron/scheduler)
4. Implement data quality checks
5. Create weather trend analysis algorithms
6. Build rainfall prediction model
7. Integrate with ROS for ETo calculations
8. Implement severe weather alerts

## API Endpoints

### Weather Data Endpoints
```
# Current weather
GET /api/v1/weather/current
GET /api/v1/weather/station/{stationId}/current

# Historical data
GET /api/v1/weather/history?start={date}&end={date}
GET /api/v1/weather/station/{stationId}/history

# Analytics
GET /api/v1/weather/trends/temperature?days=7
GET /api/v1/weather/rainfall/accumulated?period=monthly
GET /api/v1/weather/forecast/rainfall?hours=24

# Alerts
GET /api/v1/weather/alerts/active
POST /api/v1/weather/alerts/subscribe
```

## Testing Commands

```bash
# Test weather data ingestion
curl -X POST http://localhost:3003/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "deviceId": "AOS-ST001",
    "type": "weather",
    "data": {
      "temperature": 28.5,
      "humidity": 75,
      "rainfall": 2.5,
      "windSpeed": 5.2
    }
  }'

# Get current weather
curl http://localhost:3006/api/v1/weather/current

# Get rainfall trends
curl http://localhost:3006/api/v1/weather/rainfall/accumulated?period=daily&days=7

# Check weather alerts
curl http://localhost:3006/api/v1/weather/alerts/active
```

## Integration Points

### With ROS Service (Instance 6)
```javascript
// Provide weather data for ETo calculation
export async function getWeatherForETo(date: Date, location: Location) {
  return {
    temperature: { min: 22, max: 35, mean: 28 },
    humidity: { min: 60, max: 85, mean: 72 },
    windSpeed: 2.5,  // at 2m height
    solarRadiation: 22.5,  // MJ/m²/day
    pressure: 1013  // hPa
  };
}
```

### With External API (Instance 5)
```javascript
// Expose weather data via unified API
router.get('/api/v1/sensors/aos/latest', async (req, res) => {
  const weatherData = await weatherService.getCurrentWeather();
  res.json(formatForExternalAPI(weatherData));
});
```

## Data Quality Checks
1. Temperature: -10°C to 50°C
2. Humidity: 0% to 100%
3. Pressure: 900 to 1100 hPa
4. Wind Speed: 0 to 50 m/s
5. Rainfall: 0 to 500 mm/hour

## Notes for Development
- Handle missing data gracefully (sensor failures)
- Implement data interpolation for gaps
- Cache frequently accessed data
- Use weather station metadata for validation
- Consider elevation in temperature adjustments
- Implement sunrise/sunset calculations
- Add weather icon mappings for UI