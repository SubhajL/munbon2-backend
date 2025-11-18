# Moisture Graphs System Architecture Summary

## Overview
Frontend-moisture-graphs.html provides real-time visualization of soil moisture sensor data with support for raw and smoothed data views, multiple sensors, and configurable time periods.

---

## Data Flow Architecture

### 1. Database Layer (TimescaleDB)
**Tables:**
- `moisture_readings` - Raw sensor data
- `smoothed_moisture_readings` - Smoothed/filtered data
- `water_control_smartfarm.smartfarm_plots` - Plot metadata (in munbon_dev)
- `water_control_smartfarm.smartfarm_sensor_plot_mapping` - Sensor-to-plot mappings
- `water_control_smartfarm.smartfarm_plot_moisture_thresholds` - Moisture thresholds

**Key Columns in moisture_readings:**
- `time` - Timestamp (timestamptz)
- `sensor_id` - Sensor identifier (e.g., "0001-0001")
- `moisture_surface_pct` - Surface moisture percentage
- `moisture_deep_pct` - Deep moisture percentage
- `temp_surface_c`, `temp_deep_c` - Temperature readings
- `ambient_humidity_pct`, `ambient_temp_c` - Ambient conditions
- `voltage` - Battery voltage
- `location_lat`, `location_lng` - GPS coordinates
- `flood_status` - Boolean flood indicator
- `quality_score` - Data quality metric

---

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATABASE LAYER                              │
├─────────────────────────────────────────────────────────────────────┤
│ TimescaleDB (sensor_data)                                           │
│   - moisture_readings                                               │
│   - smoothed_moisture_readings                                      │
│                                                                      │
│ PostgreSQL (munbon_dev)                                             │
│   - water_control_smartfarm.smartfarm_plots                         │
│   - water_control_smartfarm.smartfarm_sensor_plot_mapping           │
│   - water_control_smartfarm.smartfarm_plot_moisture_thresholds      │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      BACKEND SERVICE LAYER                          │
├─────────────────────────────────────────────────────────────────────┤
│ sensor-data service (Node.js/TypeScript)                            │
│   Port: 3001                                                        │
│                                                                      │
│ 1. moisture.routes.ts                                               │
│    └─ GET /api/v1/moisture/chart                                    │
│                                                                      │
│ 2. moisture-chart-data.service.ts                                   │
│    └─ getMoistureChartData()                                        │
│       - Aggregates in 15-min buckets                                │
│       - UNION raw + smoothed data                                   │
│       - Normalizes sensor IDs                                       │
│                                                                      │
│ 3. moisture-chart-formatter.ts                                      │
│    └─ formatChartDataBySensor()                                     │
│       - Groups by sensor_id                                         │
│       - Converts timezone                                           │
│       - Separates raw vs smoothed                                   │
│                                                                      │
│ 4. smartfarm.repository.ts                                          │
│    └─ Fetches plot mappings & thresholds                            │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼ HTTP/JSON
┌─────────────────────────────────────────────────────────────────────┐
│                         API ENDPOINT                                │
├─────────────────────────────────────────────────────────────────────┤
│ GET /api/v1/moisture/chart                                          │
│   ?period=24h                                                       │
│   &timeZone=Asia/Bangkok                                            │
│   &includeSmoothed=true                                             │
│   &sensorIds=0001-0001,0001-0002 (optional)                         │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER                               │
├─────────────────────────────────────────────────────────────────────┤
│ frontend-moisture-graphs.html                                       │
│   Served via: Python HTTP server on port 8080                       │
│                                                                      │
│ Components:                                                         │
│   - Chart.js 4.4.0 (visualization)                                  │
│   - frontend-config.js (API config)                                 │
│   - Auto-refresh: 60 seconds                                        │
│   - Modes: Raw | Smoothed | Both                                    │
│   - Sensors: 0001-0001 through 0001-0012                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Backend Service Layer (Node.js/TypeScript)

### Service: sensor-data
**Location:** `/services/sensor-data/`

**Key Files:**

1. **`src/routes/moisture.routes.ts`** (Line 420-481)
   - GET `/api/v1/moisture/chart` endpoint
   - Query params: `period`, `sensorIds`, `timeZone`, `includeSmoothed`

2. **`src/services/moisture-chart-data.service.ts`**
   - `getMoistureChartData()` - Fetches data from database
   - Aggregates data in 15-minute buckets
   - Supports UNION of raw + smoothed data when `includeSmoothed=true`
   - Normalizes sensor IDs (e.g., "0001-0001" → "MS-00001-00001")

3. **`src/transformers/moisture-chart-formatter.ts`**
   - `formatChartDataBySensor()` - Formats data for frontend
   - Groups by sensor_id
   - Converts timestamps to local timezone (Asia/Bangkok)
   - Separates raw vs smoothed data points
   - Enriches with plot metadata and thresholds

4. **`src/repository/smartfarm.repository.ts`**
   - `getPlotMappingsBySensorIds()` - Maps sensors to plots
   - `getThresholdsByPlotIds()` - Fetches moisture thresholds

---

## API Endpoint

**URL:** `GET http://localhost:3001/api/v1/moisture/chart`

**Query Parameters:**
- `period` - Time range: `24h`, `3d`, `7d`, `14d` (required)
- `sensorIds` - Comma-separated sensor IDs (optional, defaults to all)
- `timeZone` - Timezone for timestamps (default: `UTC`)
- `includeSmoothed` - Include smoothed data: `true`/`false` (default: `false`)

**Example Request:**
```
GET http://localhost:3001/api/v1/moisture/chart?period=24h&timeZone=Asia/Bangkok&includeSmoothed=true
```

**Response Structure:**
```json
{
  "aggregation": {
    "interval": "15 minutes",
    "method": "average"
  },
  "period": "24h",
  "timeRange": {
    "start": "2025-11-17T02:00:00.000Z",
    "end": "2025-11-18T02:00:00.000Z"
  },
  "localTimeZone": "Asia/Bangkok",
  "sensors": {
    "0001-0001": {
      "sensorId": "0001-0001",
      "plotId": "PLOT-001",
      "thresholds": {
        "lower": 30,
        "upper": 70
      },
      "dataPoints": [
        {
          "time": "2025-11-17T09:00:00+07:00",
          "avgMoistureSurface": 45.5,
          "minMoistureSurface": 43.2,
          "maxMoistureSurface": 47.8,
          "avgMoistureDeep": 52.3,
          "minMoistureDeep": 50.1,
          "maxMoistureDeep": 54.5,
          "sampleCount": 12
        }
      ],
      "smoothedDataPoints": [
        {
          "time": "2025-11-17T09:00:00+07:00",
          "avgMoistureSurface": 45.2,
          "avgMoistureDeep": 52.1,
          "sampleCount": 12
        }
      ],
      "stats": {
        "totalSamples": 288,
        "timeRange": {
          "start": "2025-11-17T09:00:00+07:00",
          "end": "2025-11-18T09:00:00+07:00"
        }
      }
    }
  },
  "summary": {
    "totalSensors": 12,
    "totalDataPoints": 576
  }
}
```

---

## Frontend Layer (HTML/JavaScript)

**File:** `/frontend-moisture-graphs.html`

**Dependencies:**
- Chart.js 4.4.0 - Chart rendering
- chartjs-adapter-date-fns 3.0.0 - Time series support
- frontend-config.js - API configuration

**Key Features:**

1. **API Configuration** (Line 232)
   - Default: `http://localhost:3001/api/v1`
   - Configurable via URL param: `?api=http://custom:3001/api/v1`
   - Persisted in localStorage as `MUNBON_API_BASE`

2. **Sensor List** (Line 233-246)
   - Hardcoded 12 sensors: `0001-0001` through `0001-0012`
   - Auto-displays all sensors if none configured

3. **Data Fetching** (Line 252-268)
   - `fetchMoistureData(period)` - Calls `/moisture/chart` API
   - Always requests `includeSmoothed=true`
   - Timezone: `Asia/Bangkok`

4. **Chart Modes** (Line 250, 313-358)
   - **Raw** - Shows raw sensor data only
   - **Smoothed** - Shows filtered/smoothed data only
   - **Both** - Overlays raw + smoothed
   - Mode persisted per-sensor in localStorage

5. **Data Visualization** (Line 287-358)
   - Surface moisture: Teal solid line (`rgb(20, 184, 166)`)
   - Deep moisture: Pink dashed line (`rgb(236, 72, 153)`)
   - Smoothed surface: Blue bold line (`rgb(2, 132, 199)`)
   - Smoothed deep: Purple dashed bold line (`rgb(139, 92, 246)`)
   - Lower threshold: Red line (`rgb(220, 38, 38)`)
   - Upper threshold: Yellow line (`rgb(234, 179, 8)`)

6. **Auto-Refresh** (Line 595-602)
   - Refreshes every 60 seconds
   - Manual refresh button available

7. **Statistics Display** (Line 270-284, 490-516)
   - Min/Max/Average for surface & deep moisture
   - Sample count per sensor
   - Plot ID mapping

---

## Environment Variables & Configuration

### Backend (.env file location: `/services/sensor-data/.env`)

```bash
# TimescaleDB - Sensor Data (Primary)
TIMESCALE_HOST=43.208.201.191
TIMESCALE_PORT=5432
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=P@ssw0rd123!
TIMESCALE_DB=sensor_data

# Config Database - Plot Mappings & Thresholds
CONFIG_DB_HOST=43.208.201.191
CONFIG_DB_PORT=5432
CONFIG_DB_NAME=munbon_dev
CONFIG_DB_USER=postgres
CONFIG_DB_PASSWORD=P@ssw0rd123!
CONFIG_DB_SCHEMA=water_control_smartfarm

# Server Configuration
PORT=3001
NODE_ENV=development

# MQTT (not used by moisture charts)
MQTT_PORT=1883
MQTT_WS_PORT=8083

# CORS
CORS_ORIGIN=http://localhost:3000,http://localhost:3001
```

### Frontend Configuration

**Via URL Parameter:**
```
http://localhost:8080/frontend-moisture-graphs.html?api=http://localhost:3001/api/v1
```

**Via LocalStorage:**
```javascript
localStorage.setItem('MUNBON_API_BASE', 'http://localhost:3001/api/v1');
```

**Via frontend-config.js:**
- Priority: URL param > localStorage > default
- Default: `http://localhost:3001/api/v1`

---

## Required Setup

### 1. Database Setup
```sql
-- Ensure tables exist in TimescaleDB
-- moisture_readings (hypertable on 'time')
-- smoothed_moisture_readings (hypertable on 'time')

-- Ensure config tables exist in munbon_dev
-- water_control_smartfarm.smartfarm_plots
-- water_control_smartfarm.smartfarm_sensor_plot_mapping
-- water_control_smartfarm.smartfarm_plot_moisture_thresholds
```

### 2. Backend Service
```bash
cd /services/sensor-data
npm install
npm run dev  # Port 3001
```

### 3. Frontend Server
```bash
# From project root
python3 -m http.server 8080
```

### 4. Access
```
Frontend: http://localhost:8080/frontend-moisture-graphs.html
API:      http://localhost:3001/api/v1/moisture/chart
```

---

## Data Aggregation Details

**Time Buckets:** 15 minutes
**Aggregation Method:** AVG, MIN, MAX
**Query Performance:**
- Uses TimescaleDB time_bucket() for efficient aggregation
- Indexes on (time, sensor_id)
- Typical response time: < 500ms for 24h period

**Sample SQL:**
```sql
SELECT
  time_bucket('15 minutes'::interval, time) AS time,
  sensor_id,
  AVG(moisture_surface_pct) as avg_moisture_surface,
  MIN(moisture_surface_pct) as min_moisture_surface,
  MAX(moisture_surface_pct) as max_moisture_surface,
  AVG(moisture_deep_pct) as avg_moisture_deep,
  COUNT(*) as sample_count
FROM moisture_readings
WHERE time >= $1 AND time <= $2
GROUP BY time_bucket('15 minutes'::interval, time), sensor_id
ORDER BY time ASC;
```

---

## Key Integrations

1. **Smoothing System:**
   - Separate table: `smoothed_moisture_readings`
   - UNION query when `includeSmoothed=true`
   - Tagged with `source` field ('raw' or 'smoothed')

2. **SmartFarm Integration:**
   - Plot mappings from `munbon_dev` database
   - Moisture thresholds per plot
   - Enriched in API response metadata

3. **Chart.js Configuration:**
   - Time series with date-fns adapter
   - 15-min interval display
   - Interactive tooltips
   - Responsive grid layout

---

## File Structure Summary

```
/
├── frontend-moisture-graphs.html       # Main frontend
├── frontend-config.js                  # API config loader
└── services/sensor-data/
    ├── .env                            # Environment variables
    ├── src/
    │   ├── routes/
    │   │   └── moisture.routes.ts      # API endpoint (Line 420-481)
    │   ├── services/
    │   │   └── moisture-chart-data.service.ts  # Data fetching
    │   ├── transformers/
    │   │   └── moisture-chart-formatter.ts     # Data formatting
    │   ├── repository/
    │   │   ├── timescale.repository.ts         # DB queries
    │   │   └── smartfarm.repository.ts         # Plot metadata
    │   └── types/
    │       └── moisture-chart.types.ts         # TypeScript types
```

---

## Troubleshooting

**No data displayed:**
1. Check API endpoint: `curl http://localhost:3001/api/v1/moisture/chart?period=24h`
2. Verify database connectivity in .env
3. Check browser console for errors
4. Confirm sensor-data service is running on port 3001

**Wrong timezone:**
- Frontend sends `timeZone=Asia/Bangkok` by default
- Timestamps are converted server-side using dayjs

**Smoothed data missing:**
- Verify `smoothed_moisture_readings` table exists
- Check if smoothing process is running
- Ensure `includeSmoothed=true` in request

**Service not starting:**
- Check if port 3001 is already in use: `lsof -i :3001`
- Verify .env file exists and has correct values
- Check npm dependencies: `npm install`

---

## Quick Reference Commands

```bash
# Start backend service
cd services/sensor-data && npm run dev

# Start frontend server
python3 -m http.server 8080

# Test API endpoint
curl "http://localhost:3001/api/v1/moisture/chart?period=24h&includeSmoothed=true"

# Check database connectivity
psql -h 43.208.201.191 -U postgres -d sensor_data -c "SELECT COUNT(*) FROM moisture_readings;"

# View service logs (if using PM2)
pm2 logs sensor-data

# Check running processes
lsof -i :3001
lsof -i :8080
```
