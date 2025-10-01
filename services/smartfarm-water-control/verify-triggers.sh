#!/bin/bash
# Verify Smart Farm Database Triggers on AWS
# Usage: ./verify-triggers.sh

# Database connection details - set these as environment variables or update directly
PGHOST="${TIMESCALE_HOST:-postgres-aws-munbon.region.rds.amazonaws.com}"
PGPORT="${TIMESCALE_PORT:-5432}"
PGDATABASE="${TIMESCALE_DB:-sensor_data}"
PGUSER="${TIMESCALE_USER:-postgres}"
# PGPASSWORD should be set as environment variable: export PGPASSWORD=your_password

echo "=========================================="
echo "Smart Farm Trigger Verification"
echo "=========================================="
echo "Host: $PGHOST"
echo "Database: $PGDATABASE"
echo ""

echo "1. Checking trigger function definition..."
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c "
SELECT
    proname as function_name,
    pg_get_functiondef(oid) as definition
FROM pg_proc
WHERE proname = 'smartfarm_notify_reading';
"

echo ""
echo "2. Checking trigger registration status..."
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c "
SELECT
    t.tgname as trigger_name,
    CASE t.tgenabled
        WHEN 'O' THEN 'ENABLED'
        WHEN 'D' THEN 'DISABLED'
        ELSE 'UNKNOWN'
    END as status,
    c.relname as table_name,
    n.nspname as schema_name
FROM pg_trigger t
JOIN pg_class c ON t.tgrelid = c.oid
JOIN pg_namespace n ON c.relnamespace = n.oid
WHERE t.tgname IN ('trigger_notify_moisture_reading', 'trigger_notify_water_level_reading')
ORDER BY t.tgname;
"

echo ""
echo "3. Checking recent moisture readings (last 5)..."
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c "
SELECT
    sensor_id,
    moisture_percent,
    timestamp,
    NOW() - timestamp as age
FROM water_control_smartfarm.moisture_readings
ORDER BY timestamp DESC
LIMIT 5;
"

echo ""
echo "4. Checking recent water level readings (last 5)..."
psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -c "
SELECT
    sensor_id,
    water_level_cm,
    timestamp,
    NOW() - timestamp as age
FROM water_control_smartfarm.water_level_readings
ORDER BY timestamp DESC
LIMIT 5;
"

echo ""
echo "=========================================="
echo "Verification complete!"
echo "=========================================="
