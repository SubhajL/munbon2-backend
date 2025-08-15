# Display Fixes Summary

## 1. Time Storage Fix (Now Storing Bangkok Time Directly)

**UPDATE: As of August 2, 2025, timestamps are now stored directly in Bangkok time (UTC+7)**

### How to Query (Simple - No Conversion Needed!)

```sql
-- Direct query - time is already in Bangkok timezone
SELECT 
    sensor_id,
    time as bangkok_time,
    location_lat,
    location_lng,
    moisture_surface_pct,
    moisture_deep_pct
FROM moisture_readings
ORDER BY time DESC;
```

### IMPORTANT: DO NOT USE TIME ZONE CONVERSIONS
Since data is already stored in Bangkok time, using `AT TIME ZONE` will give incorrect results:

```sql
-- WRONG - Don't do this anymore!
SELECT time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok' FROM moisture_readings;

-- CORRECT - Just use time directly
SELECT time FROM moisture_readings;
```

## 2. Gateway ID Formatting Fix

Updated the consumer code to pad gateway IDs with leading zeros:
- Gateway "3" → "0003"
- Gateway "03" → "0003"
- Gateway "003" → "0003"

The fix has been deployed and will apply to all new data going forward.

## 3. For Existing Data

To update existing data in the database:

```sql
-- Update sensor IDs to have leading zeros
UPDATE moisture_readings 
SET sensor_id = 
    CASE 
        WHEN sensor_id = '3-13' THEN '0003-13'
        WHEN sensor_id = '03-13' THEN '0003-13'
        WHEN sensor_id = '003-13' THEN '0003-13'
        ELSE sensor_id
    END
WHERE sensor_id IN ('3-13', '03-13', '003-13');

-- Do the same for sensor_registry
UPDATE sensor_registry 
SET sensor_id = 
    CASE 
        WHEN sensor_id = '3-13' THEN '0003-13'
        WHEN sensor_id = '03-13' THEN '0003-13'
        WHEN sensor_id = '003-13' THEN '0003-13'
        ELSE sensor_id
    END
WHERE sensor_id IN ('3-13', '03-13', '003-13');
```

## Results
- ✅ Times now display in Bangkok local time (UTC+7)
- ✅ Gateway IDs are padded with leading zeros (e.g., "3" → "0003")
- ✅ Sensor IDs follow format: "0003-13" instead of "3-13"