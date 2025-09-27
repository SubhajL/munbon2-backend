#!/bin/bash

echo "=== Checking ALL Data in EC2 Database from Last 15 Days ==="
echo "Date: $(date)"
echo ""

# Configuration
EC2_IP="43.208.201.191"
SSH_KEY="~/dev/th-lab01.pem"

echo "1. Checking database connectivity..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -c "\l" | grep sensor_data || echo "Database check failed"
EOF

echo ""
echo "2. Listing all tables in sensor_data database..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
EOF

echo ""
echo "3. Checking water_level_readings table (last 15 days)..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
SELECT 
    COUNT(*) as total_records,
    MIN(time) as oldest_record,
    MAX(time) as newest_record,
    COUNT(DISTINCT sensor_id) as unique_sensors
FROM water_level_readings
WHERE time >= NOW() - INTERVAL '15 days';"
EOF

echo ""
echo "4. Checking moisture_readings table (last 15 days)..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
SELECT 
    COUNT(*) as total_records,
    MIN(time) as oldest_record,
    MAX(time) as newest_record,
    COUNT(DISTINCT sensor_id) as unique_sensors
FROM moisture_readings
WHERE time >= NOW() - INTERVAL '15 days';"
EOF

echo ""
echo "5. Checking weather_data table (last 15 days)..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
SELECT 
    COUNT(*) as total_records,
    MIN(time) as oldest_record,
    MAX(time) as newest_record,
    COUNT(DISTINCT sensor_id) as unique_sensors
FROM weather_data
WHERE time >= NOW() - INTERVAL '15 days';" 2>/dev/null || echo "No weather_data table found"
EOF

echo ""
echo "6. Daily data summary for all sensor types (last 15 days)..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
-- Water Level Daily Summary
SELECT 
    'water_level' as sensor_type,
    date_trunc('day', time) as day,
    COUNT(*) as daily_count
FROM water_level_readings
WHERE time >= NOW() - INTERVAL '15 days'
GROUP BY date_trunc('day', time)
ORDER BY day DESC;

-- Moisture Daily Summary
SELECT 
    'moisture' as sensor_type,
    date_trunc('day', time) as day,
    COUNT(*) as daily_count
FROM moisture_readings
WHERE time >= NOW() - INTERVAL '15 days'
GROUP BY date_trunc('day', time)
ORDER BY day DESC;"
EOF

echo ""
echo "7. Latest records from each table..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
echo "Latest Water Level Record:"
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
SELECT * FROM water_level_readings 
ORDER BY time DESC 
LIMIT 1;"

echo ""
echo "Latest Moisture Record:"
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
SELECT * FROM moisture_readings 
ORDER BY time DESC 
LIMIT 1;"
EOF

echo ""
echo "8. Checking for any other tables with time-based data..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
SELECT 
    table_name,
    column_name
FROM information_schema.columns
WHERE table_schema = 'public'
    AND data_type IN ('timestamp', 'timestamptz', 'timestamp without time zone', 'timestamp with time zone')
    AND table_name NOT IN ('water_level_readings', 'moisture_readings')
ORDER BY table_name, column_name;"
EOF

echo ""
echo "9. Checking system status and PM2 processes..."
ssh -i $SSH_KEY ubuntu@$EC2_IP "pm2 list | grep -E 'online|stopped' || echo 'PM2 check failed'"

echo ""
echo "=== Summary ==="
echo "The queries above show all available data from the EC2 database in the last 15 days."
echo "This includes water level, moisture, and any other sensor data tables."