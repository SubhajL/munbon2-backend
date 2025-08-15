#!/bin/bash

echo "=== Checking EC2 Table Schema ==="
echo ""

# EC2 PostgreSQL connection details
EC2_HOST="43.209.22.250"
EC2_PORT="5432"
EC2_DB="sensor_data"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

export PGPASSWORD=$EC2_PASSWORD

echo "1. Water Level Readings Schema on EC2:"
psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "
\d water_level_readings
"

echo ""
echo "2. Water Level Readings Schema on Local:"
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "\d water_level_readings"

echo ""
echo "3. Checking if EC2 has TimescaleDB tables:"
psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "
SELECT table_name FROM _timescaledb_catalog.hypertable WHERE schema_name = 'public';
"

echo ""
echo "4. Checking EC2 TimescaleDB version:"
psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "
SELECT default_version, installed_version FROM pg_available_extensions WHERE name = 'timescaledb';
"

unset PGPASSWORD