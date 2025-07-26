-- Check latest water level data
SELECT 
    device_id,
    water_level,
    voltage,
    rssi,
    time AT TIME ZONE 'Asia/Bangkok' as bangkok_time,
    created_at AT TIME ZONE 'Asia/Bangkok' as created_bangkok
FROM water_level_readings
ORDER BY time DESC
LIMIT 10;

-- Check latest moisture data
SELECT 
    gateway_id,
    sensor_id,
    surface_moisture,
    deep_moisture,
    surface_temp,
    deep_temp,
    time AT TIME ZONE 'Asia/Bangkok' as bangkok_time,
    created_at AT TIME ZONE 'Asia/Bangkok' as created_bangkok
FROM moisture_readings
ORDER BY time DESC
LIMIT 10;

-- Check data count by date
SELECT 
    DATE(time AT TIME ZONE 'Asia/Bangkok') as date,
    COUNT(*) as water_level_count
FROM water_level_readings
WHERE time > NOW() - INTERVAL '7 days'
GROUP BY DATE(time AT TIME ZONE 'Asia/Bangkok')
ORDER BY date DESC;

-- Check if data from today exists
SELECT 
    'Water Level' as data_type,
    COUNT(*) as today_count,
    MAX(time AT TIME ZONE 'Asia/Bangkok') as latest_time
FROM water_level_readings
WHERE DATE(time AT TIME ZONE 'Asia/Bangkok') = CURRENT_DATE
UNION ALL
SELECT 
    'Moisture' as data_type,
    COUNT(*) as today_count,
    MAX(time AT TIME ZONE 'Asia/Bangkok') as latest_time
FROM moisture_readings
WHERE DATE(time AT TIME ZONE 'Asia/Bangkok') = CURRENT_DATE;