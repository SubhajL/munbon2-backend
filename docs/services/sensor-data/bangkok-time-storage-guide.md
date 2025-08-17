# Bangkok Time Storage Guide

## Overview
As of August 2, 2025, the sensor data system now stores all timestamps in Bangkok local time (UTC+7) instead of UTC. This change was implemented to simplify data querying and display for local users.

## What Changed
1. **Timestamp Storage**: All timestamps are now stored as Bangkok time (UTC+7) in the database
2. **Gateway ID Format**: Gateway IDs are padded with leading zeros (e.g., "3" → "0003")
3. **Sensor ID Format**: Sensor IDs follow the pattern "{gateway_id}-{sensor_id}" (e.g., "0003-13")

## How to Query Data

### Direct Query (Recommended)
Since timestamps are already in Bangkok time, query them directly:

```sql
-- Get recent moisture readings
SELECT 
    sensor_id,
    time as bangkok_time,
    moisture_surface_pct,
    moisture_deep_pct
FROM moisture_readings 
WHERE time > NOW() - INTERVAL '1 hour'
ORDER BY time DESC;
```

### DO NOT Use Time Zone Conversion
Do NOT use `AT TIME ZONE` conversions as the data is already in Bangkok time:

```sql
-- WRONG - This will give incorrect results
SELECT time AT TIME ZONE 'Asia/Bangkok' FROM moisture_readings;

-- CORRECT - Use time directly
SELECT time FROM moisture_readings;
```

## Technical Details

### Database Configuration
- TimescaleDB timezone: UTC (server setting)
- Table column type: `TIMESTAMP WITHOUT TIME ZONE`
- Data stored: Bangkok time (UTC+7)

### Conversion Process
1. Sensor sends data with UTC timestamps
2. Consumer receives and parses UTC timestamp
3. Consumer adds 7 hours to convert to Bangkok time
4. Bangkok time is stored in database

### Example
- Sensor UTC time: `2025-08-01 17:54:30`
- Stored Bangkok time: `2025-08-02 00:54:30` (UTC + 7 hours)

## Viewing in DBeaver/DataGrip
Since the timestamps are already in Bangkok time, no special configuration is needed:

1. Query the `time` column directly
2. The displayed time IS Bangkok local time
3. No timezone conversion needed

## Migration of Old Data
If you need to migrate old UTC data to Bangkok time:

```sql
-- Convert existing UTC timestamps to Bangkok time
UPDATE moisture_readings 
SET time = time + INTERVAL '7 hours'
WHERE time < '2025-08-02 00:00:00';  -- Before the change
```

## API Response Format
When returning data via API, the timestamps are already in Bangkok time and should be formatted accordingly:

```json
{
  "sensor_id": "0003-13",
  "timestamp": "2025-08-02T00:54:30",  // Bangkok time
  "moisture_surface": 22.0,
  "moisture_deep": 28.0
}
```