#!/bin/bash

echo "🔍 Checking sensor registration status..."

# Use docker exec to connect to TimescaleDB
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
SELECT 
    sensor_id, 
    sensor_type, 
    manufacturer, 
    is_active, 
    last_seen,
    created_at,
    updated_at
FROM sensor_registry 
ORDER BY created_at DESC 
LIMIT 10;
"

echo -e "\n📊 Checking moisture readings count..."
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
SELECT 
    sensor_id,
    COUNT(*) as reading_count,
    MIN(time) as first_reading,
    MAX(time) as last_reading
FROM moisture_readings 
GROUP BY sensor_id
ORDER BY last_reading DESC;
"

echo -e "\n🔍 Checking sensor_readings table..."
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
SELECT 
    sensor_id,
    sensor_type,
    COUNT(*) as reading_count,
    MAX(time) as last_reading
FROM sensor_readings 
WHERE sensor_type = 'moisture'
GROUP BY sensor_id, sensor_type
ORDER BY last_reading DESC
LIMIT 10;
"