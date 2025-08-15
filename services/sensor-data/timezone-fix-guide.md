# Timezone Fix Guide

## Current Situation
- Database timezone: UTC
- Column type: `timestamp without time zone`
- Data from sensors: UTC timestamps
- Display requirement: Bangkok time (UTC+7)

## Correct Approach
1. Store timestamps as UTC in the database
2. Use timezone conversion when querying for display

## Query for Bangkok Time Display

```sql
-- Correct query for Bangkok time display
SELECT 
    sensor_id,
    time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok' as bangkok_time,
    moisture_surface_pct,
    moisture_deep_pct
FROM moisture_readings 
WHERE sensor_id = '0003-13'
ORDER BY time DESC;
```

## For DBeaver/DataGrip Users

Create this view for easy querying:

```sql
CREATE OR REPLACE VIEW moisture_readings_bangkok AS
SELECT 
    sensor_id,
    time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok' as bangkok_time,
    time as utc_time,
    location_lat,
    location_lng,
    moisture_surface_pct,
    moisture_deep_pct,
    temp_surface_c,
    temp_deep_c,
    ambient_humidity_pct,
    ambient_temp_c,
    flood_status,
    voltage,
    quality_score
FROM moisture_readings;
```

Then simply query:
```sql
SELECT * FROM moisture_readings_bangkok WHERE sensor_id = '0003-13' ORDER BY bangkok_time DESC;
```

## Understanding the Issue
The confusion arose because:
1. TimescaleDB uses `timestamp without time zone` which doesn't store timezone info
2. When we tried to add 7 hours in the application, it created incorrect timestamps
3. The proper solution is to store UTC and convert on display

## Data Flow
1. Sensor sends: "2025/08/02" + "00:17:45" (UTC)
2. Consumer stores: 2025-08-02 00:17:45 (as UTC)
3. Query displays: 2025-08-02 07:17:45 (Bangkok time)