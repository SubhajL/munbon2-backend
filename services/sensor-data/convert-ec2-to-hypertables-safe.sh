#!/bin/bash

echo "=== Safe Conversion of EC2 Tables to TimescaleDB Hypertables ==="
echo "Time: $(date -u)"
echo ""

# EC2 connection details
EC2_HOST="43.209.22.250"
EC2_USER="ubuntu"
SSH_KEY="$HOME/dev/th-lab01.pem"

echo "1. Checking existing hypertables..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
SELECT h.table_name, h.schema_name, 
       (SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema = h.schema_name 
        AND table_name = h.table_name) as exists
FROM _timescaledb_catalog.hypertable h
WHERE h.schema_name = 'public';
\""

echo ""
echo "2. Checking sensor_registry table..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
SELECT COUNT(*) as sensor_count FROM sensor_registry;
\""

echo ""
echo "3. Checking foreign key constraints..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
SELECT 
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name 
FROM 
    information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
      AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY' 
  AND tc.table_name IN ('water_level_readings', 'moisture_readings', 'sensor_location_history');
\""

echo ""
echo "4. Checking if tables are already hypertables..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
SELECT tablename, 
       CASE WHEN EXISTS (
           SELECT 1 FROM _timescaledb_catalog.hypertable h 
           WHERE h.table_name = tablename AND h.schema_name = 'public'
       ) THEN 'YES' ELSE 'NO' END as is_hypertable
FROM pg_tables 
WHERE schemaname = 'public' 
  AND tablename IN ('water_level_readings', 'moisture_readings', 'sensor_location_history');
\""

echo ""
echo "5. Getting table row counts..."
ssh -i $SSH_KEY $EC2_USER@$EC2_HOST "docker exec timescaledb psql -U postgres -d sensor_data -c \"
SELECT 'water_level_readings' as table_name, COUNT(*) as row_count FROM water_level_readings
UNION ALL
SELECT 'moisture_readings', COUNT(*) FROM moisture_readings
UNION ALL
SELECT 'sensor_location_history', COUNT(*) FROM sensor_location_history;
\""

echo ""
echo "=== Analysis Complete ===="
echo ""
echo "Based on the foreign key constraints, we need to:"
echo "1. Either populate sensor_registry with all sensor IDs"
echo "2. Or drop foreign key constraints before conversion"
echo ""
echo "Would you like to proceed with dropping foreign keys? (safer for hypertable conversion)"