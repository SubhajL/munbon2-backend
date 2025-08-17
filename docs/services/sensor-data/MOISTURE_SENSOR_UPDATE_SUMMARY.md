# Moisture Sensor Update Summary

## Date: July 29, 2025

## 1. Updates Identified from Manufacturer PDF

The moisture sensor manufacturer (M2M) has provided an updated data format with the following **NEW fields**:

### Gateway-level additions:
- `temperature`: Ambient temperature at gateway location (°C)
- `humidity`: Ambient humidity at gateway location (%)
- `heat_index`: Calculated heat index at gateway location

### Sensor-level additions:
- `flood`: Surface water detection status ("yes"/"no")
- `amb_humid`: Ambient humidity at sensor location (%)
- `amb_temp`: Ambient temperature at sensor location (°C)
- Individual `date` and `time` fields per sensor (allowing different timestamps)

## 2. Code Updates Implemented

### A. TypeScript Service Updates (`src/services/sensor-data.service.ts`)
1. Updated `detectSensorType()` to support alternative moisture format
2. Enhanced `processMoistureData()` to handle new M2M format:
   - Gateway registration with ambient data
   - New sensor ID format: `MS-XXXXX-XXXXX` (MS = Moisture Sensor)
   - Thailand date/time parsing (YYYY/MM/DD format)
   - Flood status detection and alerts
3. Updated metadata extraction to include gateway ambient conditions
4. Added `parseThailandDateTime()` helper method

### B. Data Model Updates (`src/models/sensor.model.ts`)
- Added `GATEWAY` to SensorType enum

### C. Processing Scripts Created
1. `process-moisture-new-format.js` - Processes moisture data from SQS queue with new format
2. `test-new-moisture-format.js` - Tests API endpoints with new format

## 3. Database Schema (Existing - No changes needed)

The existing `moisture_readings` table already supports all required fields:
```sql
- time (timestamp)
- sensor_id (varchar)
- moisture_surface_pct (numeric) -- Maps to humid_hi
- moisture_deep_pct (numeric)    -- Maps to humid_low
- temp_surface_c (numeric)       -- Maps to temp_hi
- temp_deep_c (numeric)          -- Maps to temp_low
- ambient_humidity_pct (numeric) -- Maps to amb_humid
- ambient_temp_c (numeric)       -- Maps to amb_temp
- flood_status (boolean)         -- Maps to flood
- voltage (numeric)              -- Maps to sensor_batt/100
- location_lat, location_lng (double precision)
- quality_score (numeric)
```

## 4. Sensor ID Mapping

New naming convention:
- Gateway: `GW-XXXXX` (e.g., GW-00001)
- Moisture Sensor: `MS-GGGGG-SSSSS` (e.g., MS-00001-00002)
  - GGGGG = Gateway ID (padded to 5 digits)
  - SSSSS = Sensor ID (padded to 5 digits)

## 5. Testing Results

✅ Successfully tested with sample data:
- Gateway GW-00001 registered with ambient data
- Sensor MS-00001-00001 data saved (no flood)
- Quality score calculation working
- Date/time parsing functioning correctly

## 6. API Endpoints

The system accepts new moisture data format at:
- Local: `POST http://localhost:3003/api/v1/munbon-m2m-moisture/telemetry`
- CloudFlare Tunnel: `POST https://munbon-moisture.beautifyai.io/api/v1/munbon-m2m-moisture/telemetry`

## 7. Alert Conditions

The system will generate alerts for:
- **LOW_MOISTURE**: When surface moisture < 20%
- **FLOOD_DETECTED**: When flood status = "yes"

## 8. Next Steps

1. ✅ Update TypeScript service to handle new format
2. ✅ Create processing scripts for new format
3. ✅ Test with sample data
4. ⏳ Deploy updated service
5. ⏳ Coordinate with manufacturer for production data
6. ⏳ Monitor incoming data for quality issues

## 9. Sample Data Format

```json
{
  "gateway_id": "00001",
  "msg_type": "interval",
  "date": "2025/07/29",
  "time": "10:30:00",
  "latitude": "13.12345",
  "longitude": "100.54621",
  "temperature": "38.50",      // NEW
  "humidity": "55",            // NEW
  "heat_index": "41.35",       // NEW
  "gw_batt": "372",
  "sensor": [
    {
      "sensor_id": "00001",
      "date": "2025/07/29",    // NEW (individual)
      "time": "10:29:15",      // NEW (individual)
      "flood": "no",           // NEW
      "amb_humid": "60",       // NEW
      "amb_temp": "40.50",     // NEW
      "humid_hi": "50",
      "temp_hi": "25.50",
      "humid_low": "72",
      "temp_low": "25.00",
      "sensor_batt": "395"
    }
  ]
}
```