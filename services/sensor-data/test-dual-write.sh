#!/bin/bash

echo "=== Testing Dual-Write Configuration ==="
echo "Time: $(date -u)"
echo ""

echo "1. Checking environment variables in consumer..."
pm2 env 15 | grep -E "ENABLE_DUAL_WRITE|EC2_DB" | head -5

echo ""
echo "2. Checking recent data in LOCAL database..."
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
SELECT 
    'water_level' as data_type,
    COUNT(*) as count_last_hour,
    MAX(time) as latest_reading
FROM water_level_readings 
WHERE time > NOW() - INTERVAL '1 hour'
UNION ALL
SELECT 
    'moisture' as data_type,
    COUNT(*) as count_last_hour,
    MAX(time) as latest_reading
FROM moisture_readings 
WHERE time > NOW() - INTERVAL '1 hour';"

echo ""
echo "3. Checking recent data in EC2 database..."
ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250 "docker exec timescaledb psql -U postgres -d sensor_data -c \"
SELECT 
    'water_level' as data_type,
    COUNT(*) as count_last_hour,
    MAX(time) as latest_reading
FROM water_level_readings 
WHERE time > NOW() - INTERVAL '1 hour'
UNION ALL
SELECT 
    'moisture' as data_type,
    COUNT(*) as count_last_hour,
    MAX(time) as latest_reading
FROM moisture_readings 
WHERE time > NOW() - INTERVAL '1 hour';\""

echo ""
echo "4. Checking consumer logs for dual-write activity..."
pm2 logs sensor-consumer --lines 10 --nostream | grep -i "dual-write result" || echo "No recent dual-write logs found"

echo ""
echo "=== End of Test ===="