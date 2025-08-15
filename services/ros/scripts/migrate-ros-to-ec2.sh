#!/bin/bash

# Migrate ROS schema and tables from local to EC2
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Local source
LOCAL_HOST="localhost"
LOCAL_PORT="5434"
LOCAL_DB="munbon_dev"
LOCAL_USER="postgres"
LOCAL_PASSWORD="postgres"

# EC2 target
EC2_HOST="43.209.22.250"
EC2_PORT="5432"
EC2_DB="munbon_dev"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

echo -e "${BLUE}=== MIGRATE ROS SCHEMA TO EC2 ===${NC}"
echo -e "${YELLOW}Source: $LOCAL_HOST:$LOCAL_PORT/$LOCAL_DB${NC}"
echo -e "${YELLOW}Target: $EC2_HOST:$EC2_PORT/$EC2_DB${NC}"
echo ""

# Step 1: Create ROS schema on EC2
echo -e "${BLUE}Step 1: Creating ROS schema on EC2...${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB << EOF
CREATE SCHEMA IF NOT EXISTS ros;

-- Create update trigger function if not exists
CREATE OR REPLACE FUNCTION ros.update_updated_at_column()
RETURNS TRIGGER AS \$\$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
\$\$ language 'plpgsql';
EOF

# Step 2: Export ROS schema structure from local
echo -e "\n${BLUE}Step 2: Exporting ROS schema structure...${NC}"
PGPASSWORD=$LOCAL_PASSWORD pg_dump -h $LOCAL_HOST -p $LOCAL_PORT -U $LOCAL_USER \
    -d $LOCAL_DB \
    -n ros \
    --schema-only \
    --no-owner \
    --no-privileges \
    -f /tmp/ros_schema_structure.sql

# Step 3: Import schema structure to EC2
echo -e "\n${BLUE}Step 3: Importing schema structure to EC2...${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB < /tmp/ros_schema_structure.sql

# Step 4: Export ROS data from local
echo -e "\n${BLUE}Step 4: Exporting ROS data...${NC}"
PGPASSWORD=$LOCAL_PASSWORD pg_dump -h $LOCAL_HOST -p $LOCAL_PORT -U $LOCAL_USER \
    -d $LOCAL_DB \
    -n ros \
    --data-only \
    --no-owner \
    --no-privileges \
    --disable-triggers \
    -f /tmp/ros_schema_data.sql

# Get file size
DATA_SIZE=$(ls -lh /tmp/ros_schema_data.sql | awk '{print $5}')
echo -e "${GREEN}Data export complete. Size: $DATA_SIZE${NC}"

# Step 5: Import data to EC2
echo -e "\n${BLUE}Step 5: Importing ROS data to EC2...${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB < /tmp/ros_schema_data.sql

# Step 6: Verify migration
echo -e "\n${BLUE}Step 6: Verifying migration...${NC}"
echo -e "${YELLOW}Tables in ROS schema:${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'ros' 
ORDER BY tablename;"

echo -e "\n${YELLOW}Record counts:${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB << EOF
SELECT 'plot_water_demand_weekly' as table_name, COUNT(*) as record_count FROM ros.plot_water_demand_weekly
UNION ALL
SELECT 'plot_water_demand_seasonal', COUNT(*) FROM ros.plot_water_demand_seasonal
UNION ALL
SELECT 'water_demand_calculations', COUNT(*) FROM ros.water_demand_calculations
UNION ALL
SELECT 'plots', COUNT(*) FROM ros.plots
UNION ALL
SELECT 'plot_crop_schedule', COUNT(*) FROM ros.plot_crop_schedule
ORDER BY table_name;
EOF

# Step 7: Export GIS schema water demand table
echo -e "\n${BLUE}Step 7: Migrating GIS water demand table...${NC}"
PGPASSWORD=$LOCAL_PASSWORD pg_dump -h $LOCAL_HOST -p $LOCAL_PORT -U $LOCAL_USER \
    -d $LOCAL_DB \
    -t gis.ros_water_demands \
    --no-owner \
    --no-privileges \
    -f /tmp/gis_water_demands.sql

# Check if GIS schema exists on EC2
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "CREATE SCHEMA IF NOT EXISTS gis;"

# Import GIS water demand table
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB < /tmp/gis_water_demands.sql

echo -e "\n${YELLOW}GIS water demand table count:${NC}"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -c "SELECT COUNT(*) FROM gis.ros_water_demands;"

# Clean up
rm -f /tmp/ros_schema_structure.sql /tmp/ros_schema_data.sql /tmp/gis_water_demands.sql

echo -e "\n${GREEN}✅ Migration complete!${NC}"
echo -e "${BLUE}Connection info for EC2:${NC}"
echo -e "Host: $EC2_HOST"
echo -e "Port: $EC2_PORT"
echo -e "Database: $EC2_DB"
echo -e "User: $EC2_USER"
echo -e "Schema: ros"