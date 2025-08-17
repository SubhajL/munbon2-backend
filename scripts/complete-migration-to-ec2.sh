#!/bin/bash

# Complete migration script - Local to EC2
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# EC2 Target
EC2_HOST="${EC2_HOST:-43.208.201.191}"
EC2_PORT="5432"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

echo -e "${BLUE}=== COMPLETE LOCAL TO EC2 MIGRATION ===${NC}"
echo -e "${YELLOW}Target: $EC2_HOST:$EC2_PORT${NC}"
echo ""

# Step 1: Create databases on EC2
echo -e "${BLUE}Step 1: Creating databases on EC2...${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -c "CREATE DATABASE munbon_dev;" 2>/dev/null || echo "munbon_dev already exists"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -c "CREATE DATABASE sensor_data;" 2>/dev/null || echo "sensor_data already exists"

# Step 2: Enable extensions
echo -e "\n${BLUE}Step 2: Enabling required extensions...${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev << EOF
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
EOF

PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data << EOF
CREATE EXTENSION IF NOT EXISTS timescaledb;
EOF

# Step 3: Migrate munbon_dev from port 5434
echo -e "\n${BLUE}Step 3: Migrating munbon_dev database...${NC}"
echo "Creating full dump of munbon_dev..."
docker exec munbon-postgres pg_dump -U postgres -d munbon_dev \
    --no-owner \
    --no-privileges \
    --verbose \
    --no-comments \
    > /tmp/munbon_dev_complete.sql 2>/dev/null

echo "Importing to EC2..."
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev < /tmp/munbon_dev_complete.sql

# Step 4: Migrate sensor_data from port 5433
echo -e "\n${BLUE}Step 4: Migrating sensor_data database...${NC}"
echo "Creating full dump of sensor_data..."
docker exec munbon-timescaledb pg_dump -U postgres -d sensor_data \
    --no-owner \
    --no-privileges \
    --verbose \
    --no-comments \
    --exclude-schema='_timescaledb_catalog' \
    --exclude-schema='_timescaledb_internal' \
    --exclude-schema='_timescaledb_config' \
    --exclude-schema='_timescaledb_cache' \
    > /tmp/sensor_data_complete.sql 2>/dev/null

echo "Importing to EC2..."
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data < /tmp/sensor_data_complete.sql

# Step 5: Verify migration
echo -e "\n${BLUE}Step 5: Verifying migration...${NC}"

echo -e "\n${YELLOW}munbon_dev on EC2:${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev << EOF
SELECT n.nspname as schema_name, 
       COUNT(c.*) as table_count,
       (SELECT SUM((xpath('/row/count/text()', 
                          query_to_xml(format('SELECT COUNT(*) FROM %I.%I', n.nspname, c.relname), 
                                      true, true, '')))[1]::text::int)
        FROM pg_class c2 
        WHERE c2.relnamespace = n.oid AND c2.relkind = 'r') as total_rows
FROM pg_namespace n
JOIN pg_class c ON n.oid = c.relnamespace
WHERE c.relkind = 'r' 
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
GROUP BY n.nspname
ORDER BY n.nspname;
EOF

echo -e "\n${YELLOW}sensor_data on EC2:${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d sensor_data << EOF
SELECT n.nspname as schema_name, 
       COUNT(c.*) as table_count,
       (SELECT SUM((xpath('/row/count/text()', 
                          query_to_xml(format('SELECT COUNT(*) FROM %I.%I', n.nspname, c.relname), 
                                      true, true, '')))[1]::text::int)
        FROM pg_class c2 
        WHERE c2.relnamespace = n.oid AND c2.relkind = 'r') as total_rows
FROM pg_namespace n
JOIN pg_class c ON n.oid = c.relnamespace
WHERE c.relkind = 'r' 
  AND n.nspname NOT IN ('pg_catalog', 'information_schema', '_timescaledb_catalog', '_timescaledb_internal', '_timescaledb_config', '_timescaledb_cache')
GROUP BY n.nspname
ORDER BY n.nspname;
EOF

echo -e "\n${GREEN}Migration complete!${NC}"
echo -e "${YELLOW}Connection details for DBeaver:${NC}"
echo "Host: $EC2_HOST"
echo "Port: $EC2_PORT"
echo "Username: $EC2_USER"
echo "Password: $EC2_PASSWORD"
echo "Databases: munbon_dev, sensor_data"