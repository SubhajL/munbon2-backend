-- Query to display moisture readings with local Thailand time (UTC+7)
-- and properly formatted sensor IDs

SELECT 
    sensor_id,
    time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok' as local_time,
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
FROM moisture_readings
WHERE sensor_id LIKE '%-13'  -- Filter for sensor 13
ORDER BY time DESC
LIMIT 100;

-- Alternative: If you want to see both UTC and local time
SELECT 
    sensor_id,
    time as utc_time,
    time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok' as bangkok_time,
    moisture_surface_pct,
    moisture_deep_pct
FROM moisture_readings
WHERE sensor_id LIKE '%-13'
ORDER BY time DESC
LIMIT 100;

-- To update DataGrip to always show local time:
-- 1. In DataGrip, go to Database Navigator
-- 2. Right-click on the moisture_readings table
-- 3. Select "Modify Table"
-- 4. For the 'time' column, you can create a generated column or view

-- Create a view with Bangkok local time
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