#!/bin/bash

# Local database consolidation script
# Migrates databases from ports 5433 and 5434 to port 5432

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Target database credentials - EC2 PostgreSQL
TARGET_HOST="${EC2_HOST:-43.208.201.191}"
TARGET_PORT="5432"
TARGET_USER="postgres"
TARGET_PASSWORD="${TARGET_PASSWORD:-P@ssw0rd123!}"  # Can be overridden by environment variable

echo -e "${BLUE}=== Local Database Consolidation ===${NC}"
echo -e "${YELLOW}Target: $TARGET_HOST:$TARGET_PORT${NC}"

# Check if target PostgreSQL is accessible
echo -e "\n${BLUE}1. Testing connection to target database...${NC}"
PGPASSWORD=$TARGET_PASSWORD psql -h $TARGET_HOST -p $TARGET_PORT -U $TARGET_USER -c "SELECT version();" || {
    echo -e "${RED}Failed to connect to target database on $TARGET_HOST:$TARGET_PORT${NC}"
    echo "Please ensure PostgreSQL is running and accessible"
    exit 1
}

echo -e "\n${BLUE}2. Creating databases in target...${NC}"
databases=(
    "sensor_data"
    "auth_db"
    "gis_db"
    "ros_db"
    "rid_db"
    "weather_db"
    "awd_db"
)

for db in "${databases[@]}"; do
    echo -e "${YELLOW}Creating database: $db${NC}"
    PGPASSWORD=$TARGET_PASSWORD psql -h $TARGET_HOST -p $TARGET_PORT -U $TARGET_USER -c "CREATE DATABASE $db;" 2>/dev/null || echo "Database $db already exists"
done

echo -e "\n${BLUE}3. Migrating data from containers...${NC}"

# Migrate from munbon-timescaledb (5433)
if docker ps | grep -q munbon-timescaledb; then
    echo -e "${YELLOW}Migrating from munbon-timescaledb (port 5433)...${NC}"
    
    # Check which databases exist and have data
    for db in sensor_data; do
        if docker exec munbon-timescaledb psql -U postgres -lqt | cut -d \| -f 1 | grep -qw $db; then
            table_count=$(docker exec munbon-timescaledb psql -U postgres -d $db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | xargs)
            if [ "$table_count" -gt "0" ]; then
                echo "Migrating $db ($table_count tables)..."
                docker exec munbon-timescaledb pg_dump -U postgres -d $db --no-owner --no-acl | PGPASSWORD=$TARGET_PASSWORD psql -h $TARGET_HOST -p $TARGET_PORT -U $TARGET_USER -d $db
                echo -e "${GREEN}✓ $db migrated${NC}"
            else
                echo "$db has no tables, skipping"
            fi
        fi
    done
fi

# Migrate from munbon-postgres (5434)
if docker ps | grep -q munbon-postgres; then
    echo -e "${YELLOW}Migrating from munbon-postgres (port 5434)...${NC}"
    
    for db in auth_db gis_db ros_db rid_db weather_db awd_db; do
        if docker exec munbon-postgres psql -U postgres -lqt | cut -d \| -f 1 | grep -qw $db; then
            table_count=$(docker exec munbon-postgres psql -U postgres -d $db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | xargs)
            if [ "$table_count" -gt "0" ]; then
                echo "Migrating $db ($table_count tables)..."
                docker exec munbon-postgres pg_dump -U postgres -d $db --no-owner --no-acl | PGPASSWORD=$TARGET_PASSWORD psql -h $TARGET_HOST -p $TARGET_PORT -U $TARGET_USER -d $db
                echo -e "${GREEN}✓ $db migrated${NC}"
            else
                echo "$db has no tables, skipping"
            fi
        fi
    done
fi

echo -e "\n${BLUE}4. Enabling required extensions...${NC}"
# Enable TimescaleDB for sensor_data
echo "Enabling TimescaleDB for sensor_data..."
PGPASSWORD=$TARGET_PASSWORD psql -h $TARGET_HOST -p $TARGET_PORT -U $TARGET_USER -d sensor_data -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;" 2>/dev/null || echo "TimescaleDB extension already exists or not available"

# Enable PostGIS for gis_db
echo "Enabling PostGIS for gis_db..."
PGPASSWORD=$TARGET_PASSWORD psql -h $TARGET_HOST -p $TARGET_PORT -U $TARGET_USER -d gis_db -c "CREATE EXTENSION IF NOT EXISTS postgis;" 2>/dev/null || echo "PostGIS extension already exists or not available"

echo -e "\n${BLUE}5. Verifying migration...${NC}"
echo -e "${YELLOW}Databases in target:${NC}"
PGPASSWORD=$TARGET_PASSWORD psql -h $TARGET_HOST -p $TARGET_PORT -U $TARGET_USER -c "\l" | grep -E "sensor_data|auth_db|gis_db|ros_db|rid_db|weather_db|awd_db"

echo -e "\n${BLUE}6. Testing connections and counting tables...${NC}"
for db in "${databases[@]}"; do
    printf "%-15s: " "$db"
    table_count=$(PGPASSWORD=$TARGET_PASSWORD psql -h $TARGET_HOST -p $TARGET_PORT -U $TARGET_USER -d $db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | xargs || echo "0")
    if [ -n "$table_count" ] && [ "$table_count" -gt "0" ]; then
        echo -e "${GREEN}✓ Connected - $table_count tables${NC}"
    else
        echo -e "${YELLOW}✓ Connected - Empty${NC}"
    fi
done

echo -e "\n${GREEN}Local consolidation complete!${NC}"
echo -e "${YELLOW}All databases are now available on $TARGET_HOST:$TARGET_PORT${NC}"
echo -e "${YELLOW}You can stop the old containers if desired:${NC}"
echo "  docker stop munbon-timescaledb munbon-postgres"