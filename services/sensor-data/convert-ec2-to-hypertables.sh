#!/bin/bash

echo "=== Converting EC2 Tables to TimescaleDB Hypertables ==="
echo "Time: $(date -u)"
echo ""

# EC2 connection details
EC2_HOST="43.209.22.250"
EC2_USER="ubuntu"
SSH_KEY="$HOME/dev/th-lab01.pem"

echo "1. Checking TimescaleDB extension on EC2..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c 'SELECT extname, extversion FROM pg_extension WHERE extname = '\''timescaledb'\'';'"

echo ""
echo "2. Creating hypertables (with data migration)..."
echo ""

# Convert water_level_readings
echo "Converting water_level_readings to hypertable..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
SELECT create_hypertable('water_level_readings', 'time', 
    migrate_data => true,
    if_not_exists => true
);
\""

# Convert moisture_readings
echo ""
echo "Converting moisture_readings to hypertable..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
SELECT create_hypertable('moisture_readings', 'time', 
    migrate_data => true,
    if_not_exists => true
);
\""

# Convert sensor_location_history
echo ""
echo "Converting sensor_location_history to hypertable..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
SELECT create_hypertable('sensor_location_history', 'timestamp', 
    migrate_data => true,
    if_not_exists => true
);
\""

echo ""
echo "3. Verifying hypertables..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
SELECT hypertable_name, hypertable_schema 
FROM timescaledb_information.hypertables 
WHERE hypertable_schema = 'public';
\""

echo ""
echo "4. Checking table statistics..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    n_live_tup as row_count
FROM pg_stat_user_tables 
WHERE schemaname = 'public' 
    AND tablename IN ('water_level_readings', 'moisture_readings', 'sensor_location_history')
ORDER BY tablename;
\""

echo ""
echo "=== Conversion Complete ==="