#!/bin/bash

# Direct migration of ROS schema using SQL dumps
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Credentials
LOCAL_CONN="postgresql://postgres:postgres@localhost:5434/munbon_dev"
EC2_CONN="postgresql://postgres:P%40ssw0rd123%21@43.209.22.250:5432/munbon_dev"

echo -e "${BLUE}=== MIGRATE ROS SCHEMA TO EC2 ===${NC}"
echo -e "${YELLOW}Source: localhost:5434/munbon_dev${NC}"
echo -e "${YELLOW}Target: 43.209.22.250:5432/munbon_dev${NC}"
echo ""

# Step 1: Create schema on EC2
echo -e "${BLUE}Step 1: Creating ROS schema on EC2...${NC}"
psql "$EC2_CONN" << 'EOF'
CREATE SCHEMA IF NOT EXISTS ros;
CREATE SCHEMA IF NOT EXISTS gis;

-- Create trigger function
CREATE OR REPLACE FUNCTION ros.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';
EOF

# Step 2: Export schema and data
echo -e "\n${BLUE}Step 2: Exporting ROS schema from local...${NC}"
pg_dump "$LOCAL_CONN" \
    -n ros \
    --no-owner \
    --no-privileges \
    --if-exists \
    --clean \
    -f /tmp/ros_full_dump.sql

# Also export gis.ros_water_demands if it exists
echo -e "\n${BLUE}Step 3: Exporting GIS water demands table...${NC}"
pg_dump "$LOCAL_CONN" \
    -t gis.ros_water_demands \
    --no-owner \
    --no-privileges \
    --if-exists \
    -f /tmp/gis_water_demands.sql 2>/dev/null || echo "No gis.ros_water_demands table found"

# Step 3: Import to EC2
echo -e "\n${BLUE}Step 4: Importing to EC2...${NC}"
psql "$EC2_CONN" < /tmp/ros_full_dump.sql

if [ -f /tmp/gis_water_demands.sql ]; then
    psql "$EC2_CONN" < /tmp/gis_water_demands.sql
fi

# Step 4: Verify
echo -e "\n${BLUE}Step 5: Verifying migration...${NC}"
psql "$EC2_CONN" << 'EOF'
-- Show tables and counts
SELECT 
    schemaname,
    tablename,
    n_live_tup as estimated_rows
FROM pg_stat_user_tables
WHERE schemaname IN ('ros', 'gis')
ORDER BY schemaname, tablename;

-- Specific counts for important tables
\echo ''
\echo 'Exact record counts:'
SELECT 'ros.plot_water_demand_weekly' as table_name, COUNT(*) FROM ros.plot_water_demand_weekly
UNION ALL
SELECT 'ros.plot_water_demand_seasonal', COUNT(*) FROM ros.plot_water_demand_seasonal
UNION ALL  
SELECT 'ros.water_demand_calculations', COUNT(*) FROM ros.water_demand_calculations
ORDER BY table_name;
EOF

# Clean up
rm -f /tmp/ros_full_dump.sql /tmp/gis_water_demands.sql

echo -e "\n${GREEN}✅ Migration complete!${NC}"