#!/bin/bash

# Migrate ROS schema using PostgreSQL 15 tools
set -e

# Add PostgreSQL 15 to PATH
export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Local source
LOCAL_HOST="localhost"
LOCAL_PORT="5434"
LOCAL_DB="munbon_dev"
LOCAL_USER="postgres"
LOCAL_PASSWORD="postgres"

# EC2 target
EC2_HOST="${EC2_HOST:-43.208.201.191}"
EC2_PORT="5432"
EC2_DB="munbon_dev"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

echo -e "${BLUE}=== MIGRATE ROS SCHEMA TO EC2 (PostgreSQL 15) ===${NC}"
echo -e "${YELLOW}Using pg_dump version: $(pg_dump --version)${NC}"
echo ""

# Step 1: Create schemas on EC2
echo -e "${BLUE}Step 1: Ensuring schemas exist on EC2...${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB << EOF
CREATE SCHEMA IF NOT EXISTS ros;
CREATE SCHEMA IF NOT EXISTS gis;
EOF

# Step 2: Export ROS schema from local
echo -e "\n${BLUE}Step 2: Exporting ROS schema from local...${NC}"
PGPASSWORD=$LOCAL_PASSWORD pg_dump -h $LOCAL_HOST -p $LOCAL_PORT -U $LOCAL_USER \
    -d $LOCAL_DB \
    -n ros \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    -f /tmp/ros_schema_dump.sql

# Get file size
SIZE=$(ls -lh /tmp/ros_schema_dump.sql | awk '{print $5}')
echo -e "${GREEN}✓ Exported ROS schema: $SIZE${NC}"

# Step 3: Export GIS water demands table
echo -e "\n${BLUE}Step 3: Exporting GIS water demands table...${NC}"
PGPASSWORD=$LOCAL_PASSWORD pg_dump -h $LOCAL_HOST -p $LOCAL_PORT -U $LOCAL_USER \
    -d $LOCAL_DB \
    -t gis.ros_water_demands \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    -f /tmp/gis_water_demands_dump.sql 2>/dev/null || echo "No gis.ros_water_demands table found"

# Step 4: Import to EC2
echo -e "\n${BLUE}Step 4: Importing to EC2...${NC}"
echo "Importing ROS schema..."
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB < /tmp/ros_schema_dump.sql

if [ -f /tmp/gis_water_demands_dump.sql ]; then
    echo "Importing GIS water demands..."
    PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB < /tmp/gis_water_demands_dump.sql
fi

# Step 5: Verify migration
echo -e "\n${BLUE}Step 5: Verifying migration...${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB << 'EOF'
-- Check tables
\echo 'Tables in ROS schema:'
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size('ros.' || tablename)) as size
FROM pg_tables 
WHERE schemaname = 'ros' 
ORDER BY tablename;

\echo ''
\echo 'Record counts for key tables:'
SELECT 'ros.plot_water_demand_weekly' as table_name, COUNT(*) as records FROM ros.plot_water_demand_weekly
UNION ALL
SELECT 'ros.plot_water_demand_seasonal', COUNT(*) FROM ros.plot_water_demand_seasonal
UNION ALL
SELECT 'ros.water_demand_calculations', COUNT(*) FROM ros.water_demand_calculations
UNION ALL
SELECT 'ros.plots', COUNT(*) FROM ros.plots
UNION ALL
SELECT 'ros.plot_crop_schedule', COUNT(*) FROM ros.plot_crop_schedule;

-- Check GIS water demands
SELECT 'gis.ros_water_demands', COUNT(*) FROM gis.ros_water_demands;
EOF

# Clean up
rm -f /tmp/ros_schema_dump.sql /tmp/gis_water_demands_dump.sql

echo -e "\n${GREEN}✅ Migration complete!${NC}"
echo -e "${BLUE}Connection info:${NC}"
echo -e "Host: $EC2_HOST"
echo -e "Port: $EC2_PORT"
echo -e "Database: $EC2_DB"
echo -e "Schema: ros"