#!/bin/bash

# Fix TimescaleDB import for sensor_readings table
# This script handles the hypertable import issue

EC2_HOST="43.209.12.182"
EC2_PORT="5432"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

echo "=== Fixing TimescaleDB hypertable import ==="
echo ""

# First, let's check if sensor_readings is a hypertable
echo "Checking if sensor_readings is a hypertable..."
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data << EOF
SELECT * FROM timescaledb_information.hypertables 
WHERE hypertable_name = 'sensor_readings';
EOF

echo ""
echo "Converting hypertable back to regular table for import..."

# Convert hypertable back to regular table, import data, then recreate hypertable
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data << 'EOF'
-- First, drop the hypertable (this preserves the table structure)
SELECT drop_chunks('sensor_readings', older_than => '1900-01-01'::timestamptz);
SELECT remove_hypertable('sensor_readings');

-- Clear any existing data
TRUNCATE TABLE public.sensor_readings;

-- Now the table is regular, we can import data
\echo 'Table converted to regular table, ready for import'
EOF

echo ""
echo "Importing sensor_readings data..."
cd /Users/subhajlimanond/dev/munbon2-backend/csv_exports
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "\COPY public.sensor_readings FROM 'sensor_data/public_sensor_readings.csv' WITH CSV HEADER"

echo ""
echo "Converting back to hypertable..."
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data << 'EOF'
-- Recreate as hypertable
SELECT create_hypertable('sensor_readings', 'time', if_not_exists => TRUE);

-- Verify the data was imported
SELECT COUNT(*) as row_count FROM public.sensor_readings;
EOF

echo ""
echo "Import complete!"