#!/bin/bash

# Import data via temporary table approach for TimescaleDB
# This avoids the hypertable insert blocker

EC2_HOST="43.209.12.182"
EC2_PORT="5432"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

echo "=== Importing sensor data via temporary table ==="
echo ""

# Create a temporary table and import data there first
echo "Creating temporary table and importing data..."
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data << 'EOF'
-- Create temporary table with same structure
CREATE TEMP TABLE temp_sensor_readings (
    time TIMESTAMP WITHOUT TIME ZONE,
    sensor_id VARCHAR(255),
    sensor_type VARCHAR(50),
    location_lat DOUBLE PRECISION,
    location_lng DOUBLE PRECISION,
    value JSONB,
    metadata JSONB,
    quality_score DOUBLE PRECISION
);

-- Import CSV data into temp table
\COPY temp_sensor_readings FROM 'sensor_data/public_sensor_readings.csv' WITH CSV HEADER

-- Check imported data
SELECT COUNT(*) as imported_rows FROM temp_sensor_readings;

-- Clear existing data in hypertable
TRUNCATE TABLE public.sensor_readings;

-- Insert from temp table to hypertable
INSERT INTO public.sensor_readings 
SELECT * FROM temp_sensor_readings;

-- Verify final count
SELECT COUNT(*) as final_count FROM public.sensor_readings;
EOF

echo ""
echo "Now importing other tables..."

# Import other non-hypertable tables
cd /Users/subhajlimanond/dev/munbon2-backend/csv_exports

# sensor_registry
echo -n "Importing sensor_registry... "
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "TRUNCATE TABLE public.sensor_registry CASCADE;"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "\COPY public.sensor_registry FROM 'sensor_data/sensor_registry.csv' WITH CSV HEADER"
echo "Done"

# Import sensor schema tables
echo ""
echo "Creating sensor schema if not exists..."
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "CREATE SCHEMA IF NOT EXISTS sensor;"

# Create sensor tables if they don't exist
echo "Creating sensor schema tables..."
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data << 'EOF'
-- Create sensors table
CREATE TABLE IF NOT EXISTS sensor.sensors (
    sensor_id VARCHAR(255) PRIMARY KEY,
    sensor_type VARCHAR(50),
    location_lat DOUBLE PRECISION,
    location_lng DOUBLE PRECISION,
    region VARCHAR(100),
    zone VARCHAR(50),
    installation_date TIMESTAMPTZ,
    last_maintenance TIMESTAMPTZ,
    calibration_data JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Create readings table  
CREATE TABLE IF NOT EXISTS sensor.readings (
    time TIMESTAMPTZ NOT NULL,
    sensor_id VARCHAR(255),
    value DOUBLE PRECISION,
    unit VARCHAR(50),
    quality_score DOUBLE PRECISION,
    raw_data JSONB
);
EOF

# Import sensor.sensors
echo -n "Importing sensor.sensors... "
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "TRUNCATE TABLE sensor.sensors CASCADE;"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "\COPY sensor.sensors FROM 'sensor_data/sensor_sensors.csv' WITH CSV HEADER"
echo "Done"

# Import sensor.readings
echo -n "Importing sensor.readings... "
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "TRUNCATE TABLE sensor.readings CASCADE;"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "\COPY sensor.readings FROM 'sensor_data/sensor_readings.csv' WITH CSV HEADER"
echo "Done"

# Final verification
echo ""
echo "=== Final Verification ==="
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data << EOF
SELECT 'public.sensor_readings' as table_name, COUNT(*) as row_count FROM public.sensor_readings
UNION ALL
SELECT 'public.sensor_registry', COUNT(*) FROM public.sensor_registry
UNION ALL
SELECT 'sensor.sensors', COUNT(*) FROM sensor.sensors
UNION ALL  
SELECT 'sensor.readings', COUNT(*) FROM sensor.readings
ORDER BY table_name;
EOF

echo ""
echo "Import complete! Check DBeaver to see the data."