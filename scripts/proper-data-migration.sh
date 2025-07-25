#!/bin/bash

# Proper data migration script - includes actual data
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# EC2 Target
EC2_HOST="43.209.12.182"
EC2_PORT="5432"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

echo -e "${BLUE}=== Complete Data Migration to EC2 ===${NC}"

# Function to count rows
count_rows() {
    local container=$1
    local db=$2
    local schema=$3
    local table=$4
    docker exec $container psql -U postgres -d $db -t -c "SELECT COUNT(*) FROM $schema.$table;" 2>/dev/null | xargs || echo "0"
}

echo -e "\n${BLUE}1. Creating munbon_dev database on EC2...${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -c "CREATE DATABASE munbon_dev;" 2>/dev/null || echo "Database already exists"

echo -e "\n${BLUE}2. Migrating munbon_dev from local port 5434...${NC}"
if docker ps | grep -q munbon-postgres; then
    echo "Dumping munbon_dev with all data..."
    # Use pg_dump with data
    docker exec munbon-postgres pg_dump -U postgres -d munbon_dev --no-owner --no-privileges --verbose 2>/dev/null | \
        PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev -v ON_ERROR_STOP=1
    echo -e "${GREEN}✓ munbon_dev migrated${NC}"
fi

echo -e "\n${BLUE}3. Migrating sensor_data with actual data...${NC}"
if docker ps | grep -q munbon-timescaledb; then
    # First, clear existing empty tables
    echo "Clearing existing empty tables in sensor_data..."
    PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data << EOF
DROP SCHEMA IF EXISTS sensor CASCADE;
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
CREATE SCHEMA sensor;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA sensor TO postgres;
EOF

    echo "Dumping sensor_data with all data..."
    # Dump with full data
    docker exec munbon-timescaledb pg_dump -U postgres -d sensor_data --no-owner --no-privileges --verbose 2>/dev/null | \
        PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -v ON_ERROR_STOP=1
    echo -e "${GREEN}✓ sensor_data migrated${NC}"
fi

echo -e "\n${BLUE}4. Verifying data migration...${NC}"

# Check munbon_dev
echo -e "\n${YELLOW}munbon_dev database:${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev -c "
SELECT schemaname || '.' || tablename as table_name, 
       (xpath('/row/count/text()', xml_count))[1]::text::int as row_count
FROM (
    SELECT schemaname, tablename, 
           query_to_xml(format('SELECT COUNT(*) FROM %I.%I', schemaname, tablename), true, true, '') as xml_count
    FROM pg_tables 
    WHERE schemaname IN ('auth', 'gis', 'ros')
) t
WHERE (xpath('/row/count/text()', xml_count))[1]::text::int > 0
ORDER BY row_count DESC;"

# Check sensor_data
echo -e "\n${YELLOW}sensor_data database:${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data -c "
SELECT schemaname || '.' || tablename as table_name, 
       (xpath('/row/count/text()', xml_count))[1]::text::int as row_count
FROM (
    SELECT schemaname, tablename, 
           query_to_xml(format('SELECT COUNT(*) FROM %I.%I', schemaname, tablename), true, true, '') as xml_count
    FROM pg_tables 
    WHERE schemaname IN ('public', 'sensor')
) t
WHERE (xpath('/row/count/text()', xml_count))[1]::text::int > 0
ORDER BY row_count DESC;"

echo -e "\n${GREEN}Migration complete!${NC}"
echo -e "${YELLOW}Databases migrated to EC2 ($EC2_HOST:$EC2_PORT):${NC}"
echo "- munbon_dev (with auth, gis, ros schemas)"
echo "- sensor_data (with sensor readings)"
echo ""
echo "Connection details:"
echo "Host: $EC2_HOST"
echo "Port: $EC2_PORT"
echo "Username: $EC2_USER"
echo "Password: $EC2_PASSWORD"
echo "Databases: munbon_dev, sensor_data"