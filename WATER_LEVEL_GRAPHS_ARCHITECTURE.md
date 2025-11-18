# Water Level Graphs System Architecture

Complete documentation of the water level monitoring and smoothing system.

## 📋 System Overview

**Purpose**: Real-time water level monitoring with Hampel Filter + EMA smoothing across 6 AWD sensors

**Data Flow**: Database (TimescaleDB) → Backend API (Node.js/TypeScript) → Frontend (HTML/Chart.js)

---

## 🗄️ Database Layer

### Tables

1. **`water_level_readings`** (Hypertable)
   - Primary table for raw water level sensor data
   - Columns: `time`, `sensor_id`, `level_cm`, `voltage`, `rssi`, `temperature`, `location_lat`, `location_lng`
   - Source: IoT water level sensors (AWD series)
   - Partitioned by time for efficient querying

2. **`smoothed_water_level_readings`** (Hypertable)
   - Stores smoothed water level data using Hampel Filter + EMA
   - Same schema as raw readings + `quality_score`
   - Populated by: Real-time trigger + backfill script
   - Quality scoring: 50-100 based on data completeness and outlier detection

3. **`smoothing_params`**
   - Configuration table for smoothing algorithm parameters
   - Columns: `sensor_id`, `w` (window size), `kx`, `kv` (Hampel thresholds), `alpha` (EMA weight)
   - Supports wildcards: sensor-specific, `AWD-*`, or `*` (global defaults)
   - Default params: w=12, kx=2.5, kv=3.5, alpha=0.30

### Database Connection

- **Host**: 43.208.201.191
- **Port**: 5432 (TimescaleDB)
- **Database**: `sensor_data`
- **User**: postgres

---

## ⚙️ Backend Service (sensor-data)

### Service Configuration

- **Port**: 3001
- **Base Path**: `/api/v1`
- **Framework**: Express.js with TypeScript
- **ORM**: None (raw SQL via pg)

### API Endpoint

**GET `/api/v1/water-levels/chart`**

Location: `src/routes/water-level.routes.ts:366-423`

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `period` | string | Yes | - | Time period: `24h`, `3d`, `7d`, `14d` |
| `sensorIds` | string | No | all sensors | Comma-separated sensor IDs (e.g., `AWD-6D47,AWD-9950`) |
| `timeZone` | string | No | `UTC` | Timezone for time range (e.g., `Asia/Bangkok`) |
| `includeSmoothed` | boolean | No | `false` | Include smoothed data in response |

#### Example Request

```bash
GET http://localhost:3001/api/v1/water-levels/chart?period=24h&sensorIds=AWD-6D47,AWD-9950&timeZone=Asia/Bangkok&includeSmoothed=true
```

#### Response Format

```json
{
  "aggregation": {
    "interval": "15 minutes",
    "method": "average"
  },
  "period": "24h",
  "timeRange": {
    "start": "2025-11-17T01:23:33.864Z",
    "end": "2025-11-18T01:23:33.864Z"
  },
  "localTimeZone": "Asia/Bangkok",
  "sensors": {
    "AWD-6D47": {
      "sensorId": "AWD-6D47",
      "plotId": null,
      "dataPoints": [
        {
          "time": "2025-11-17T09:00:00.000Z",
          "avgLevel": 17,
          "minLevel": 17,
          "maxLevel": 17,
          "avgQuality": 1,
          "sampleCount": 3
        }
      ],
      "smoothedDataPoints": [
        {
          "time": "2025-11-17T09:00:00.000Z",
          "avgLevel": 17,
          "minLevel": 17,
          "maxLevel": 17,
          "avgQuality": 100,
          "sampleCount": 3
        }
      ],
      "stats": {
        "totalSamples": 99,
        "timeRange": {
          "start": "2025-11-17T01:23:33.864Z",
          "end": "2025-11-18T01:23:33.864Z"
        }
      }
    }
  },
  "summary": {
    "totalSensors": 1,
    "totalDataPoints": 33
  }
}
```

### Backend Components

#### 1. Routes Layer
**File**: `src/routes/water-level.routes.ts`

- Main endpoint handler at line 366
- Request validation and parameter parsing
- Calls service layer for data fetching
- Uses formatter for response transformation

#### 2. Service Layer
**File**: `src/services/water-level-chart-data.service.ts`

Key method: `getWaterLevelChartData(period, sensorIds?, includeSmoothed?)`

**Data aggregation logic**:
- 15-minute intervals for 24h and 3d periods
- 1-hour intervals for 7d and 14d periods
- Calculates: AVG, MIN, MAX, sample count, quality score
- UNION ALL query when `includeSmoothed=true` to combine raw + smoothed data

**SQL Query Structure** (when includeSmoothed=true):
```sql
WITH combined AS (
  -- Raw data
  SELECT
    time_bucket('15 minutes', time) AS time,
    sensor_id,
    AVG(level_cm) as avg_level,
    MIN(level_cm) as min_level,
    MAX(level_cm) as max_level,
    AVG(1) as avg_quality,
    COUNT(*) as sample_count,
    'raw' as source
  FROM water_level_readings
  WHERE time >= $1 AND time <= $2
  GROUP BY time_bucket('15 minutes', time), sensor_id

  UNION ALL

  -- Smoothed data
  SELECT
    time_bucket('15 minutes', time) AS time,
    sensor_id,
    AVG(level_cm) as avg_level,
    MIN(level_cm) as min_level,
    MAX(level_cm) as max_level,
    AVG(quality_score) as avg_quality,
    COUNT(*) as sample_count,
    'smoothed' as source
  FROM smoothed_water_level_readings
  WHERE time >= $1 AND time <= $2
  GROUP BY time_bucket('15 minutes', time), sensor_id
)
SELECT * FROM combined
ORDER BY time ASC, sensor_id, source;
```

#### 3. Formatter Layer
**File**: `src/transformers/water-level-chart-formatter.ts`

**Key function**: `formatChartDataBySensor(rows, period, timeRange, localTimeZone)`

Transforms database rows into frontend-ready structure:
- Groups by sensor_id
- Separates raw and smoothed data by `source` field
- Populates `dataPoints` array (raw data)
- Populates `smoothedDataPoints` array (smoothed data)
- Calculates per-sensor statistics

#### 4. Types
**File**: `src/types/water-level-chart.types.ts`

Key types:
- `WaterLevelReadingRow` - Database row with optional `source: 'raw' | 'smoothed'`
- `WaterLevelChartResponse` - Complete API response structure
- `SensorChartData` - Per-sensor data with dataPoints and smoothedDataPoints arrays

---

## 🎨 Frontend

### Deployment

- **Server**: Python HTTP server
- **Port**: 8080
- **File**: `frontend-water-level-graphs.html`
- **URL**: http://localhost:8080/frontend-water-level-graphs.html

### Features

1. **6 Water Level Sensors**
   - AWD-6D47
   - AWD-9950
   - AWD-B89D
   - AWD-558F
   - AWD-4ED4
   - AWD-A4F8

2. **Display Modes** (per sensor + global)
   - **Raw**: Show only raw data (blue line)
   - **Smoothed**: Show only smoothed data (red/pink line)
   - **Both**: Show both raw and smoothed (default)

3. **Time Periods**
   - Last 24 Hours (default)
   - Last 3 Days
   - Last 7 Days
   - Last 14 Days

4. **Chart Features**
   - Chart.js with date-fns adapter
   - Bangkok timezone conversion (UTC+7)
   - Interactive tooltips and legends
   - Responsive grid layout (2-3 columns)

5. **Statistics Panel** (per sensor)
   - Latest reading
   - Average
   - Minimum
   - Maximum

6. **Auto-refresh**: Every 30 seconds

7. **Persistence**: Mode preferences saved to localStorage

### Color Scheme

- **Raw data**: Blue `rgb(54, 162, 235)` - solid line
- **Smoothed data**: Red/Pink `rgb(255, 99, 132)` - thicker line with dashes

### Frontend Architecture

```
frontend-water-level-graphs.html
├── HTML Structure
│   ├── Header (title + back button)
│   ├── Controls (period selector + global mode toggle + refresh)
│   ├── Sensors Grid (6 sensor panels)
│   └── Last Update Timestamp
│
├── JavaScript Functions
│   ├── fetchWaterLevelData(period)
│   ├── renderSensors(data)
│   ├── createModeToggle(sensorId, hasSmoothed)
│   ├── updateSensorChart(sensorId)
│   ├── assembleWaterLevelDatasets(mode, dataPoints, smoothedDataPoints)
│   ├── toBangkokTime(utcDate)
│   └── refreshData()
│
└── Chart.js Configuration
    ├── Type: line
    ├── Time scale with Bangkok timezone
    ├── Tooltips with formatted times
    └── Legend per sensor
```

---

## 🔧 Smoothing Infrastructure

### Algorithm: Hampel Filter + EMA

**Step 1: Outlier Detection (Hampel Filter)**
- Window size (w): 12 readings
- Calculate rolling median and MAD (Median Absolute Deviation)
- Threshold: |value - median| > kx × max(MAD, 0.5)
- Default kx = 2.5

**Step 2: Value Cleaning**
- Outliers replaced with median
- Negative values and values > 200 cm marked as outliers
- Ensures non-negative cleaned values

**Step 3: Exponential Moving Average (EMA)**
- Formula: `smoothed[i] = α × cleaned[i] + (1-α) × smoothed[i-1]`
- Default alpha (α) = 0.30
- Time-gap adjustment: reduce alpha for gaps > 1 hour

**Step 4: Quality Scoring**
- 100%: Full window of data
- 90%: ≥75% of window
- 80%: ≥50% of window
- 70%: ≥3 readings
- 50%: Less than 3 readings
- Reduced 10% if outlier detected

### SQL Migration Files

Located in: `services/sensor-data/sql/water-level/`

1. **01_create_smoothed_table.sql**
   - Creates `smoothed_water_level_readings` hypertable
   - Identical schema to raw table + quality_score
   - Primary key: (sensor_id, time)

2. **02_profile_quality_raw.sql**
   - Quality profiling queries for raw data
   - Checks for nulls, negatives, outliers

3. **03_profile_quality_smoothed.sql**
   - Quality profiling for smoothed data
   - Validates smoothing effectiveness

4. **04_backfill_smoothing_14d.sql**
   - Backfills last 14 days of smoothed data
   - Uses recursive CTE for per-sensor processing
   - Applies full Hampel + EMA algorithm
   - Runtime: ~2-3 seconds for 6 sensors

5. **06_create_smoothing_params.sql**
   - Creates `smoothing_params` configuration table
   - Inserts default parameters for AWD-* sensors
   - Supports sensor-specific tuning

6. **07_realtime_smoothing_fn_and_trigger.sql**
   - Creates `fn_smooth_water_level_row()` trigger function
   - Implements full smoothing algorithm in PL/pgSQL
   - Trigger: `trigger_smooth_water_level` on INSERT to water_level_readings
   - Automatically smooths incoming data

### Migration Execution

**Script**: `sql/water-level/run-water-level-migrations.sh`

```bash
cd services/sensor-data/sql/water-level
./run-water-level-migrations.sh
```

**Execution order**:
1. Create smoothed table
2. Create smoothing params table
3. Insert default params
4. Backfill 14 days
5. Create trigger function and trigger

---

## 🔐 Environment Variables

Required in: `services/sensor-data/.env`

```env
# TimescaleDB Connection
TIMESCALE_HOST=43.208.201.191
TIMESCALE_PORT=5432
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=P@ssw0rd123!

# Server Configuration
PORT=3001
NODE_ENV=development

# Optional: Logging
LOG_LEVEL=info
```

---

## 🚀 Quick Start

### Prerequisites

```bash
# Ensure TimescaleDB is accessible
psql -h 43.208.201.191 -p 5432 -U postgres -d sensor_data -c "SELECT 1"

# Verify tables exist
psql -h 43.208.201.191 -p 5432 -U postgres -d sensor_data -c "
SELECT tablename FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('water_level_readings', 'smoothed_water_level_readings')
"
```

### 1. Run Migrations (First Time Only)

```bash
cd services/sensor-data/sql/water-level
./run-water-level-migrations.sh
```

**Expected output**:
- ✓ Smoothed table created
- ✓ Smoothing params created
- ✓ Backfilled ~1992 smoothed records
- ✓ Trigger created and verified

### 2. Start Backend

```bash
cd services/sensor-data
npm install  # if needed
npm run dev
```

**Verify**:
```bash
curl "http://localhost:3001/api/v1/water-levels/chart?period=24h&includeSmoothed=true" | jq '.summary'
```

Expected response:
```json
{
  "totalSensors": 6,
  "totalDataPoints": 204
}
```

### 3. Start Frontend

```bash
cd /Users/subhajlimanond/dev/munbon2-backend
python3 -m http.server 8080
```

**Access**:
- Frontend: http://localhost:8080/frontend-water-level-graphs.html
- Should see 6 sensors with both raw and smoothed data

---

## 📊 Data Verification

### Check Raw Data

```sql
SELECT sensor_id, COUNT(*) as count,
       MIN(time) as first_reading,
       MAX(time) as last_reading
FROM water_level_readings
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY sensor_id
ORDER BY sensor_id;
```

### Check Smoothed Data

```sql
SELECT sensor_id, COUNT(*) as count,
       AVG(quality_score) as avg_quality,
       MIN(time) as first_reading,
       MAX(time) as last_reading
FROM smoothed_water_level_readings
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY sensor_id
ORDER BY sensor_id;
```

### Verify Trigger

```sql
SELECT trigger_name, event_object_table, action_timing, event_manipulation
FROM information_schema.triggers
WHERE trigger_name = 'trigger_smooth_water_level';
```

Expected: 1 row with AFTER INSERT trigger

---

## 🧪 Testing

### Unit Tests

```bash
cd services/sensor-data
npm test -- water-level
```

**Test files**:
- `src/routes/water-level.routes.spec.ts` - API endpoint tests
- `src/services/water-level-chart-data.service.spec.ts` - Service layer tests
- `src/services/water-level-chart-data.service.includeSmoothed.spec.ts` - Smoothing tests
- `src/transformers/water-level-chart-formatter.spec.ts` - Formatter tests

### Integration Tests

```bash
npm test -- water-level-smoothing
```

**Test file**: `test/integration/water-level-smoothing.spec.ts`

Validates:
- Smoothing reduces variance
- Quality scores are calculated correctly
- Raw and smoothed data can be fetched together

---

## 🐛 Troubleshooting

### Issue: No Smoothed Data

**Check trigger status**:
```sql
SELECT * FROM information_schema.triggers
WHERE trigger_name = 'trigger_smooth_water_level';
```

**Recreate trigger**:
```bash
cd services/sensor-data
node recreate-trigger.js
```

### Issue: Frontend Not Loading

**Check backend**:
```bash
curl http://localhost:3001/api/v1/water-levels/chart?period=24h
```

**Check Python server**:
```bash
lsof -i :8080  # Should show Python process
```

### Issue: Wrong Timezone

Frontend converts UTC to Bangkok (UTC+7) using `toBangkokTime()` function. Verify:
```javascript
// In browser console
const utc = new Date('2025-11-17T09:00:00.000Z');
console.log(utc.toLocaleString('en-US', {timeZone: 'Asia/Bangkok'}));
// Should show: 11/17/2025, 4:00:00 PM
```

---

## 📈 Performance Metrics

### API Response Time
- 24h period: ~200-300ms
- 7d period: ~400-500ms
- 14d period: ~600-800ms

### Database Query Performance
- Raw data aggregation: ~50-100ms
- Smoothed data aggregation: ~50-100ms
- Combined (UNION ALL): ~150-250ms

### Frontend Rendering
- Initial load: ~500ms
- Chart rendering (6 sensors): ~200-300ms
- Mode switching: <100ms (chart destroy + recreate)

---

## 🔄 Comparison: Water Level vs Moisture

| Feature | Water Level | Moisture |
|---------|-------------|----------|
| **Sensors** | 6 AWD sensors | 12 sensors (0001-0001 to 0001-0012) |
| **Data Fields** | 1 field (level_cm) | 2 fields (surface + deep) |
| **Smoothing** | Hampel + EMA | Same algorithm |
| **Default Mode** | Both | Raw |
| **Colors** | Blue (raw) + Red (smoothed) | Teal (surface) + Pink (deep) + Blue/Purple (smoothed) |
| **Auto-refresh** | 30 seconds | 60 seconds |
| **Adapter** | date-fns | date-fns |
| **Timezone** | Manual conversion (UTC+7) | Browser local |
| **Plot Metadata** | No (plotId always null) | Yes (from config DB) |
| **Thresholds** | No | Yes (upper/lower) |

---

## 📝 Recent Changes (2025-11-18)

1. ✅ Implemented complete smoothing infrastructure (7 SQL files)
2. ✅ Added backend API support for `includeSmoothed` parameter
3. ✅ Created frontend with Raw/Smoothed/Both modes
4. ✅ Changed default mode to "Both" for better UX
5. ✅ Improved color contrast (blue vs red/pink)
6. ✅ Added Bangkok timezone support
7. ✅ Removed debug console.log statements
8. ✅ Matched moisture graphs layout exactly

---

## 📚 Related Documentation

- Moisture Graphs: `MOISTURE_GRAPHS_ARCHITECTURE.md`
- Smoothing Algorithm: `services/sensor-data/sql/water-level/baseline_metrics.md`
- API Tests: `services/sensor-data/src/routes/water-level.routes.spec.ts`

---

**Last Updated**: 2025-11-18
**Version**: 1.0
**Maintainer**: Development Team
