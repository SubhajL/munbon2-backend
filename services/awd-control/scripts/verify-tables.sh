#!/bin/bash

# Verification script for AWD tables

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables
if [ -f "../.env" ]; then
    export $(cat ../.env | grep -v '^#' | xargs)
fi

# Database connection parameters
POSTGRES_HOST=${POSTGRES_HOST:-"43.209.22.250"}
POSTGRES_PORT=${POSTGRES_PORT:-"5432"}
POSTGRES_DB=${POSTGRES_DB:-"munbon_dev"}
POSTGRES_USER=${POSTGRES_USER:-"postgres"}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-"P@ssw0rd123!"}

TIMESCALE_DB=${TIMESCALE_DB:-"sensor_data"}

echo "======================================"
echo "AWD Tables Verification"
echo "======================================"
echo ""

echo -e "${YELLOW}PostgreSQL Tables in munbon_dev (schema: awd):${NC}"
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT 
    table_schema,
    table_name,
    (SELECT COUNT(*) FROM awd.awd_fields) as awd_fields_count,
    (SELECT COUNT(*) FROM awd.awd_configurations) as awd_config_count,
    (SELECT COUNT(*) FROM awd.awd_sensors) as awd_sensors_count
FROM information_schema.tables 
WHERE table_schema = 'awd' 
ORDER BY table_name
LIMIT 1;"

echo ""
echo -e "${YELLOW}All AWD tables in PostgreSQL:${NC}"
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'awd' 
ORDER BY table_name;"

echo ""
echo -e "${YELLOW}TimescaleDB Tables in sensor_data:${NC}"
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $TIMESCALE_DB -c "
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('awd_sensor_readings', 'irrigation_events', 'awd_water_level_hourly')
ORDER BY table_name;"

echo ""
echo -e "${YELLOW}Hypertables in sensor_data:${NC}"
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $TIMESCALE_DB -c "
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public' 
AND tablename IN ('awd_sensor_readings', 'irrigation_events');"

echo ""
echo -e "${GREEN}Verification complete!${NC}"