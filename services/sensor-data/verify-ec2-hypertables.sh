#!/bin/bash

echo "=== Verifying EC2 Hypertables and Testing Dual-Write ==="
echo "Time: $(date -u)"
echo ""

# EC2 PostgreSQL connection details
EC2_HOST="43.209.22.250"
EC2_PORT="5432"
EC2_DB="sensor_data"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

export PGPASSWORD=$EC2_PASSWORD

echo "1. Checking if tables are hypertables..."
psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "
SELECT 
    tablename,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM _timescaledb_catalog.hypertable 
            WHERE table_name = tablename
        ) THEN 'YES' 
        ELSE 'NO' 
    END as is_hypertable
FROM pg_tables 
WHERE schemaname = 'public' 
  AND tablename IN ('water_level_readings', 'moisture_readings', 'sensor_location_history');
"

echo ""
echo "2. Checking hypertable details..."
psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "
SELECT 
    ht.table_name,
    ht.created
FROM _timescaledb_catalog.hypertable ht
WHERE ht.schema_name = 'public'
  AND ht.table_name IN ('water_level_readings', 'moisture_readings');
"

echo ""
echo "3. Checking recent data in EC2..."
psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "
SELECT 
    'water_level' as data_type,
    COUNT(*) as total_count,
    COUNT(CASE WHEN time > NOW() - INTERVAL '1 hour' THEN 1 END) as last_hour,
    MAX(time) as latest_time
FROM water_level_readings
UNION ALL
SELECT 
    'moisture' as data_type,
    COUNT(*) as total_count,
    COUNT(CASE WHEN time > NOW() - INTERVAL '1 hour' THEN 1 END) as last_hour,
    MAX(time) as latest_time
FROM moisture_readings;
"

echo ""
echo "4. Testing direct insert to EC2 hypertable..."
psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "
-- Test insert
INSERT INTO water_level_readings (time, sensor_id, level_cm, voltage, rssi, snr, battery_percentage, quality_score)
VALUES (NOW(), 'DUAL-WRITE-TEST', -25.5, 3.3, -70, 10, 85, 0.9)
ON CONFLICT (time, sensor_id) DO NOTHING;

-- Verify insert
SELECT time, sensor_id, level_cm 
FROM water_level_readings 
WHERE sensor_id = 'DUAL-WRITE-TEST'
ORDER BY time DESC 
LIMIT 1;

-- Cleanup
DELETE FROM water_level_readings WHERE sensor_id = 'DUAL-WRITE-TEST';
"

echo ""
echo "5. Restarting consumer to test dual-write..."
echo "  Restarting sensor-consumer with dual-write enabled..."
cd /Users/subhajlimanond/dev/munbon2-backend/services/sensor-data
pm2 restart sensor-consumer --update-env

sleep 3

echo ""
echo "6. Checking consumer logs for dual-write..."
pm2 logs sensor-consumer --lines 20 --nostream | grep -E "dual-write|EC2|error" | tail -10

echo ""
echo "=== Verification Complete ==="
unset PGPASSWORD