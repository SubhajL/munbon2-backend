#!/bin/bash

echo "=== Converting EC2 Tables to Hypertables with FK Handling ==="
echo "Time: $(date -u)"
echo ""

# EC2 connection details
EC2_HOST="43.209.22.250"
EC2_USER="ubuntu"
SSH_KEY="$HOME/dev/th-lab01.pem"

echo "Step 1: Dropping foreign key constraints temporarily..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
-- Drop foreign key constraints
ALTER TABLE water_level_readings DROP CONSTRAINT IF EXISTS water_level_readings_sensor_id_fkey;
ALTER TABLE moisture_readings DROP CONSTRAINT IF EXISTS moisture_readings_sensor_id_fkey;
ALTER TABLE sensor_location_history DROP CONSTRAINT IF EXISTS sensor_location_history_sensor_id_fkey;
\""

echo ""
echo "Step 2: Converting tables to hypertables..."

# Convert water_level_readings
echo "  Converting water_level_readings..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
SELECT create_hypertable('water_level_readings', 'time', 
    migrate_data => true,
    if_not_exists => true
);
\""

# Convert moisture_readings
echo "  Converting moisture_readings..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
SELECT create_hypertable('moisture_readings', 'time', 
    migrate_data => true,
    if_not_exists => true
);
\""

# Convert sensor_location_history only if it has data
echo "  Checking sensor_location_history..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
DO \\\$\\\$
BEGIN
    IF EXISTS (SELECT 1 FROM sensor_location_history LIMIT 1) THEN
        PERFORM create_hypertable('sensor_location_history', 'timestamp', 
            migrate_data => true,
            if_not_exists => true
        );
        RAISE NOTICE 'sensor_location_history converted to hypertable';
    ELSE
        RAISE NOTICE 'sensor_location_history is empty, skipping hypertable conversion';
    END IF;
END
\\\$\\\$;
\""

echo ""
echo "Step 3: Verifying hypertable creation..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
SELECT hypertable_name, hypertable_schema,
       (SELECT COUNT(*) FROM _timescaledb_catalog.chunk c 
        WHERE c.hypertable_id = h.id) as chunk_count
FROM timescaledb_information.hypertables h
WHERE hypertable_schema = 'public'
ORDER BY hypertable_name;
\""

echo ""
echo "Step 4: Testing dual-write capability..."
echo "  Inserting test record into water_level_readings..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
INSERT INTO water_level_readings (time, sensor_id, level_cm, voltage, rssi, snr, battery_percentage, quality_score)
VALUES (NOW(), 'TEST-HYPERTABLE', -50.5, 3.3, -70, 10, 85, 0.9)
ON CONFLICT (time, sensor_id) DO NOTHING;

SELECT time, sensor_id, level_cm FROM water_level_readings 
WHERE sensor_id = 'TEST-HYPERTABLE' 
ORDER BY time DESC LIMIT 1;
\""

echo ""
echo "Step 5: Cleaning up test data..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
DELETE FROM water_level_readings WHERE sensor_id = 'TEST-HYPERTABLE';
\""

echo ""
echo "=== Conversion Complete ==="
echo ""
echo "Note: Foreign key constraints have been dropped to allow hypertable conversion."
echo "The tables are now hypertables and ready for dual-write operations."