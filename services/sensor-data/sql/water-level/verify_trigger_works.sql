-- Verify trigger is working by checking recent data

-- Count recent entries in both tables
SELECT
    'Raw readings (last hour)' AS table_name,
    COUNT(*) AS count,
    MAX(time) AS latest_time
FROM water_level_readings
WHERE time > NOW() - INTERVAL '1 hour'

UNION ALL

SELECT
    'Smoothed readings (last hour)' AS table_name,
    COUNT(*) AS count,
    MAX(time) AS latest_time
FROM smoothed_water_level_readings
WHERE time > NOW() - INTERVAL '1 hour';