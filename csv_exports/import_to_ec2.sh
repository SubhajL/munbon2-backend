#!/bin/bash

# Import CSV files to EC2 PostgreSQL
# Usage: ./import_to_ec2.sh

EC2_HOST="43.209.22.250"
EC2_PORT="5432"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

echo "=== Importing sensor_data CSV files to EC2 ==="
echo "Host: $EC2_HOST"
echo "Database: sensor_data"
echo ""

# First, clear existing data to avoid duplicates
echo "Clearing existing data..."
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data << EOF
TRUNCATE TABLE public.sensor_readings CASCADE;
TRUNCATE TABLE public.sensor_registry CASCADE;
TRUNCATE TABLE public.moisture_readings CASCADE;
TRUNCATE TABLE public.sensor_calibrations CASCADE;
TRUNCATE TABLE public.sensor_location_history CASCADE;
TRUNCATE TABLE public.water_level_readings CASCADE;
EOF

# Import each CSV file
echo ""
echo "Importing public schema tables..."

# sensor_registry first (referenced by other tables)
echo -n "Importing sensor_registry... "
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "\COPY public.sensor_registry FROM 'sensor_data/sensor_registry.csv' WITH CSV HEADER"
echo "Done"

# sensor_readings
echo -n "Importing sensor_readings... "
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "\COPY public.sensor_readings FROM 'sensor_data/public_sensor_readings.csv' WITH CSV HEADER"
echo "Done"

# Other empty tables (just to ensure structure is there)
echo -n "Importing moisture_readings... "
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "\COPY public.moisture_readings FROM 'sensor_data/moisture_readings.csv' WITH CSV HEADER"
echo "Done"

echo -n "Importing sensor_calibrations... "
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "\COPY public.sensor_calibrations FROM 'sensor_data/sensor_calibrations.csv' WITH CSV HEADER"
echo "Done"

echo -n "Importing sensor_location_history... "
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "\COPY public.sensor_location_history FROM 'sensor_data/sensor_location_history.csv' WITH CSV HEADER"
echo "Done"

echo -n "Importing water_level_readings... "
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "\COPY public.water_level_readings FROM 'sensor_data/water_level_readings.csv' WITH CSV HEADER"
echo "Done"

# Also import sensor schema tables if needed
echo ""
echo "Do you also want to import sensor schema tables (sensors and readings)? (y/n)"
read -r response
if [[ "$response" == "y" ]]; then
    # Create sensor schema if not exists
    PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "CREATE SCHEMA IF NOT EXISTS sensor;"
    
    # Clear existing data
    PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data << EOF
TRUNCATE TABLE sensor.readings CASCADE;
TRUNCATE TABLE sensor.sensors CASCADE;
EOF

    echo -n "Importing sensor.sensors... "
    PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "\COPY sensor.sensors FROM 'sensor_data/sensor_sensors.csv' WITH CSV HEADER"
    echo "Done"
    
    echo -n "Importing sensor.readings... "
    PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "\COPY sensor.readings FROM 'sensor_data/sensor_readings.csv' WITH CSV HEADER"
    echo "Done"
fi

# Verify import
echo ""
echo "=== Verification ==="
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data << EOF
SELECT 'public.sensor_readings' as table_name, COUNT(*) as row_count FROM public.sensor_readings
UNION ALL
SELECT 'public.sensor_registry', COUNT(*) FROM public.sensor_registry
UNION ALL
SELECT 'public.moisture_readings', COUNT(*) FROM public.moisture_readings
UNION ALL
SELECT 'public.sensor_calibrations', COUNT(*) FROM public.sensor_calibrations
UNION ALL
SELECT 'public.sensor_location_history', COUNT(*) FROM public.sensor_location_history
UNION ALL
SELECT 'public.water_level_readings', COUNT(*) FROM public.water_level_readings
ORDER BY table_name;
EOF

echo ""
echo "Import complete! Check your DBeaver connection to sensor_data database."