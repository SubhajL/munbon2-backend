#!/bin/bash

# Import by disabling TimescaleDB triggers temporarily

EC2_HOST="43.209.12.182"
EC2_PORT="5432"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

echo "=== Importing with disabled triggers ==="
echo ""

cd /Users/subhajlimanond/dev/munbon2-backend/csv_exports

# First, let's try a different approach - import via SQL INSERT statements
echo "Converting CSV to SQL INSERT statements..."

# Convert public_sensor_readings.csv to SQL
cat > import_sensor_readings.sql << 'EOF'
-- Clear existing data
TRUNCATE TABLE public.sensor_readings;

-- Disable triggers
ALTER TABLE public.sensor_readings DISABLE TRIGGER ALL;

-- Insert data
EOF

# Convert CSV to INSERT statements
tail -n +2 sensor_data/public_sensor_readings.csv | while IFS=',' read -r time sensor_id sensor_type location_lat location_lng value metadata quality_score; do
    echo "INSERT INTO public.sensor_readings (time, sensor_id, sensor_type, location_lat, location_lng, value, metadata, quality_score) VALUES ('$time', '$sensor_id', '$sensor_type', $location_lat, $location_lng, '$value'::jsonb, '$metadata'::jsonb, $quality_score);" >> import_sensor_readings.sql
done

echo "-- Re-enable triggers" >> import_sensor_readings.sql
echo "ALTER TABLE public.sensor_readings ENABLE TRIGGER ALL;" >> import_sensor_readings.sql
echo "-- Verify" >> import_sensor_readings.sql
echo "SELECT COUNT(*) FROM public.sensor_readings;" >> import_sensor_readings.sql

# Execute the SQL
echo "Executing SQL import..."
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -f import_sensor_readings.sql

# Now do the same for sensor.readings
echo ""
echo "Converting sensor.readings CSV to SQL..."

cat > import_sensor_readings_schema.sql << 'EOF'
-- Clear existing data
TRUNCATE TABLE sensor.readings;

-- Check if it's a hypertable and disable triggers if so
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM timescaledb_information.hypertables WHERE hypertable_name = 'readings' AND hypertable_schema = 'sensor') THEN
        EXECUTE 'ALTER TABLE sensor.readings DISABLE TRIGGER ALL';
    END IF;
END $$;

-- Insert data
EOF

# Convert CSV to INSERT statements
tail -n +2 sensor_data/sensor_readings.csv | while IFS=',' read -r time sensor_id value unit quality_score raw_data; do
    # Escape single quotes in raw_data
    raw_data_escaped=$(echo "$raw_data" | sed "s/'/''/g")
    echo "INSERT INTO sensor.readings (time, sensor_id, value, unit, quality_score, raw_data) VALUES ('$time', '$sensor_id', $value, '$unit', $quality_score, '$raw_data_escaped'::jsonb);" >> import_sensor_readings_schema.sql
done

echo "-- Re-enable triggers" >> import_sensor_readings_schema.sql
echo "ALTER TABLE sensor.readings ENABLE TRIGGER ALL;" >> import_sensor_readings_schema.sql
echo "-- Verify" >> import_sensor_readings_schema.sql
echo "SELECT COUNT(*) FROM sensor.readings;" >> import_sensor_readings_schema.sql

# Execute the SQL
echo "Executing sensor.readings import..."
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -f import_sensor_readings_schema.sql

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
echo "Import complete!"