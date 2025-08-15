#!/bin/bash

# AWD Control Service Database Initialization Script
# This script creates all necessary schemas and tables for the AWD Control Service

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables
if [ -f "../.env" ]; then
    export $(cat ../.env | grep -v '^#' | xargs)
else
    echo -e "${YELLOW}Warning: .env file not found, using default values${NC}"
fi

# Database connection parameters
POSTGRES_HOST=${POSTGRES_HOST:-"43.209.22.250"}
POSTGRES_PORT=${POSTGRES_PORT:-"5432"}
POSTGRES_DB=${POSTGRES_DB:-"munbon_dev"}
POSTGRES_USER=${POSTGRES_USER:-"postgres"}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-"P@ssw0rd123!"}

TIMESCALE_HOST=${TIMESCALE_HOST:-"43.209.22.250"}
TIMESCALE_PORT=${TIMESCALE_PORT:-"5432"}
TIMESCALE_DB=${TIMESCALE_DB:-"sensor_data"}
TIMESCALE_USER=${TIMESCALE_USER:-"postgres"}
TIMESCALE_PASSWORD=${TIMESCALE_PASSWORD:-"P@ssw0rd123!"}

echo "======================================"
echo "AWD Control Service Database Setup"
echo "======================================"
echo ""

# Test PostgreSQL connection
echo -e "${YELLOW}Testing PostgreSQL connection...${NC}"
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT version();" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ PostgreSQL connection successful${NC}"
else
    echo -e "${RED}✗ Failed to connect to PostgreSQL${NC}"
    echo "  Host: $POSTGRES_HOST:$POSTGRES_PORT"
    echo "  Database: $POSTGRES_DB"
    echo "  User: $POSTGRES_USER"
    exit 1
fi

# Test TimescaleDB connection
echo -e "${YELLOW}Testing TimescaleDB connection...${NC}"
PGPASSWORD=$TIMESCALE_PASSWORD psql -h $TIMESCALE_HOST -p $TIMESCALE_PORT -U $TIMESCALE_USER -d $TIMESCALE_DB -c "SELECT version();" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ TimescaleDB connection successful${NC}"
else
    echo -e "${RED}✗ Failed to connect to TimescaleDB${NC}"
    echo "  Host: $TIMESCALE_HOST:$TIMESCALE_PORT"
    echo "  Database: $TIMESCALE_DB"
    echo "  User: $TIMESCALE_USER"
    exit 1
fi

echo ""
echo "======================================"
echo "Creating AWD Schema and Tables"
echo "======================================"

# Execute PostgreSQL schema creation
echo -e "${YELLOW}Creating AWD schema in PostgreSQL...${NC}"
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -f init-awd-schema.sql

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ AWD schema created successfully${NC}"
else
    echo -e "${RED}✗ Failed to create AWD schema${NC}"
    exit 1
fi

# Execute TimescaleDB tables creation
echo -e "${YELLOW}Creating TimescaleDB tables...${NC}"
PGPASSWORD=$TIMESCALE_PASSWORD psql -h $TIMESCALE_HOST -p $TIMESCALE_PORT -U $TIMESCALE_USER -d $TIMESCALE_DB -f init-timescale-tables.sql

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ TimescaleDB tables created successfully${NC}"
else
    echo -e "${RED}✗ Failed to create TimescaleDB tables${NC}"
    exit 1
fi

echo ""
echo "======================================"
echo "Verifying Table Creation"
echo "======================================"

# Verify PostgreSQL tables
echo -e "${YELLOW}Verifying PostgreSQL tables...${NC}"
PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT table_schema, table_name 
FROM information_schema.tables 
WHERE table_schema = 'awd' 
ORDER BY table_name;" | grep -E "(awd_fields|awd_configurations|awd_sensors|irrigation_schedules|awd_field_cycles)" > /dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All AWD tables exist in PostgreSQL${NC}"
    PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "
    SELECT table_schema, table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'awd' 
    ORDER BY table_name;"
else
    echo -e "${RED}✗ Some AWD tables are missing${NC}"
fi

# Verify TimescaleDB tables
echo ""
echo -e "${YELLOW}Verifying TimescaleDB tables...${NC}"
PGPASSWORD=$TIMESCALE_PASSWORD psql -h $TIMESCALE_HOST -p $TIMESCALE_PORT -U $TIMESCALE_USER -d $TIMESCALE_DB -c "
SELECT table_name, hypertable_name
FROM timescaledb_information.hypertables
WHERE hypertable_name IN ('awd_sensor_readings', 'irrigation_events');" | grep -E "(awd_sensor_readings|irrigation_events)" > /dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All TimescaleDB hypertables exist${NC}"
    PGPASSWORD=$TIMESCALE_PASSWORD psql -h $TIMESCALE_HOST -p $TIMESCALE_PORT -U $TIMESCALE_USER -d $TIMESCALE_DB -c "
    SELECT table_name, hypertable_name
    FROM timescaledb_information.hypertables
    WHERE hypertable_name IN ('awd_sensor_readings', 'irrigation_events');"
else
    echo -e "${RED}✗ Some TimescaleDB tables are missing${NC}"
fi

echo ""
echo "======================================"
echo -e "${GREEN}Database initialization complete!${NC}"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Start the AWD Control Service: cd .. && npm start"
echo "2. Or run in development mode: cd .. && npm run dev"
echo ""