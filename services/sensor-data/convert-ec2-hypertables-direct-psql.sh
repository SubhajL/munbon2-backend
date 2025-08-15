#!/bin/bash

echo "=== Converting EC2 Tables to Hypertables via Direct PSQL ==="
echo "Time: $(date -u)"
echo ""

# EC2 PostgreSQL connection details
EC2_HOST="43.209.22.250"
EC2_PORT="5432"
EC2_DB="sensor_data"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

export PGPASSWORD=$EC2_PASSWORD

echo "Testing connection to EC2 PostgreSQL..."
psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "SELECT version();" 2>&1 | head -1

if [ $? -ne 0 ]; then
    echo "Failed to connect to EC2 database. Network might be unreachable."
    echo "Please check your network connection and VPN if required."
    exit 1
fi

echo ""
echo "Step 1: Checking TimescaleDB extension..."
psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "
SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';
"

echo ""
echo "Step 2: Dropping foreign key constraints..."
psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "
-- Drop foreign key constraints
ALTER TABLE water_level_readings DROP CONSTRAINT IF EXISTS water_level_readings_sensor_id_fkey;
ALTER TABLE moisture_readings DROP CONSTRAINT IF EXISTS moisture_readings_sensor_id_fkey;
ALTER TABLE sensor_location_history DROP CONSTRAINT IF EXISTS sensor_location_history_sensor_id_fkey;
"

echo ""
echo "Step 3: Converting tables to hypertables..."

# Convert water_level_readings
echo "  Converting water_level_readings..."
psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "
SELECT create_hypertable('water_level_readings', 'time', 
    migrate_data => true,
    if_not_exists => true
);
"

# Convert moisture_readings
echo "  Converting moisture_readings..."
psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "
SELECT create_hypertable('moisture_readings', 'time', 
    migrate_data => true,
    if_not_exists => true
);
"

echo ""
echo "Step 4: Verifying hypertable creation..."
psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "
SELECT hypertable_name, hypertable_schema,
       (SELECT COUNT(*) FROM _timescaledb_catalog.chunk c 
        WHERE c.hypertable_id = h.id) as chunk_count
FROM timescaledb_information.hypertables h
WHERE hypertable_schema = 'public'
ORDER BY hypertable_name;
"

echo ""
echo "=== Conversion Complete ==="
unset PGPASSWORD