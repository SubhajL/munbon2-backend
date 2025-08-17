#!/bin/bash

# Import ROS tables to EC2 from CSV files
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# EC2 database
EC2_HOST="${EC2_HOST:-43.208.201.191}"
EC2_PORT="5432"
EC2_DB="munbon_dev"
EC2_USER="postgres"
EC2_PASSWORD='P@ssw0rd123!'

# Export directory
EXPORT_DIR="./ros_export"

echo -e "${BLUE}=== IMPORTING ROS TABLES TO EC2 ===${NC}"
echo -e "${YELLOW}Target: $EC2_HOST:$EC2_PORT/$EC2_DB${NC}"
echo ""

# Step 1: Create schema and tables on EC2
echo -e "${BLUE}Step 1: Creating schema and tables on EC2...${NC}"

# First, use the existing schema creation script
PGPASSWORD="$EC2_PASSWORD" psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB << 'EOF'
-- Ensure schemas exist
CREATE SCHEMA IF NOT EXISTS ros;
CREATE SCHEMA IF NOT EXISTS gis;
SET search_path TO ros, public;

-- Drop existing tables to ensure clean import
DROP TABLE IF EXISTS ros.plot_water_demand_weekly CASCADE;
DROP TABLE IF EXISTS ros.plot_water_demand_seasonal CASCADE;
DROP TABLE IF EXISTS ros.plot_crop_schedule CASCADE;
DROP TABLE IF EXISTS ros.plots CASCADE;
DROP TABLE IF EXISTS ros.water_demand_calculations CASCADE;
DROP TABLE IF EXISTS gis.ros_water_demands CASCADE;
EOF

# Create tables using the add-plot-water-demand-tables.sql script
echo -e "${YELLOW}Creating tables from schema script...${NC}"
PGPASSWORD="$EC2_PASSWORD" psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -f ./add-plot-water-demand-tables.sql

# Also create other ROS tables
PGPASSWORD="$EC2_PASSWORD" psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB << 'EOF'
SET search_path TO ros, public;

-- Create water_demand_calculations if not exists
CREATE TABLE IF NOT EXISTS ros.water_demand_calculations (
    id SERIAL PRIMARY KEY,
    area_id VARCHAR(50) NOT NULL,
    area_type VARCHAR(20) NOT NULL,
    area_name VARCHAR(100),
    calculation_date DATE NOT NULL,
    crop_type VARCHAR(50),
    growth_stage VARCHAR(50),
    eto DECIMAL(10,2),
    kc DECIMAL(4,3),
    water_demand_mm DECIMAL(10,2),
    water_demand_m3 DECIMAL(15,2),
    effective_rainfall_mm DECIMAL(10,2),
    net_water_demand_mm DECIMAL(10,2),
    net_water_demand_m3 DECIMAL(15,2),
    irrigation_efficiency DECIMAL(4,3),
    area_hectares DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create GIS water demands table
CREATE TABLE IF NOT EXISTS gis.ros_water_demands (
    id SERIAL PRIMARY KEY,
    plot_id VARCHAR(255),
    zone_name VARCHAR(255),
    section_name VARCHAR(255),
    plot_code VARCHAR(255),
    area_rai DECIMAL,
    crop_type VARCHAR(100),
    planting_date DATE,
    crop_age_days INTEGER,
    weekly_demand_m3 DECIMAL,
    monthly_demand_m3 DECIMAL,
    irrigation_efficiency DECIMAL,
    calculation_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
EOF

# Step 2: Import data from CSV files
echo -e "\n${BLUE}Step 2: Importing data from CSV files...${NC}"

# Function to import a CSV file
import_csv() {
    local schema=$1
    local table=$2
    local csv_file=$3
    
    if [[ -f "$csv_file" ]]; then
        echo -e "${YELLOW}Importing $schema.$table...${NC}"
        
        # Copy CSV to temporary location that psql can access
        temp_file="/tmp/$(basename $csv_file)"
        cp "$csv_file" "$temp_file"
        
        # Import using COPY
        PGPASSWORD="$EC2_PASSWORD" psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB << EOF
\COPY $schema.$table FROM '$temp_file' WITH CSV HEADER;
EOF
        
        # Get count
        count=$(PGPASSWORD="$EC2_PASSWORD" psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB -t -c "SELECT COUNT(*) FROM $schema.$table;")
        echo -e "${GREEN}✓ Imported $count records${NC}"
        
        # Clean up
        rm -f "$temp_file"
    else
        echo -e "${RED}Warning: $csv_file not found${NC}"
    fi
}

# Import each table
import_csv "ros" "plots" "$EXPORT_DIR/plots.csv"
import_csv "ros" "plot_crop_schedule" "$EXPORT_DIR/plot_crop_schedule.csv"
import_csv "ros" "plot_water_demand_weekly" "$EXPORT_DIR/plot_water_demand_weekly.csv"
import_csv "ros" "plot_water_demand_seasonal" "$EXPORT_DIR/plot_water_demand_seasonal.csv"
import_csv "ros" "water_demand_calculations" "$EXPORT_DIR/water_demand_calculations.csv"
import_csv "gis" "ros_water_demands" "$EXPORT_DIR/gis_ros_water_demands.csv"

# Step 3: Verify import
echo -e "\n${BLUE}Step 3: Verifying import...${NC}"
PGPASSWORD="$EC2_PASSWORD" psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d $EC2_DB << 'EOF'
\echo 'Tables and record counts:'
SELECT 
    schemaname,
    tablename,
    to_char(n_live_tup, 'FM999,999') as records
FROM pg_stat_user_tables
WHERE schemaname IN ('ros', 'gis')
  AND tablename IN ('plots', 'plot_crop_schedule', 'plot_water_demand_weekly', 
                    'plot_water_demand_seasonal', 'water_demand_calculations', 
                    'ros_water_demands')
ORDER BY schemaname, tablename;

\echo ''
\echo 'Sample data from plot_water_demand_weekly:'
SELECT plot_id, crop_week, area_rai, 
       crop_water_demand_m3_per_rai, net_water_demand_m3_per_rai
FROM ros.plot_water_demand_weekly
LIMIT 5;
EOF

echo -e "\n${GREEN}✅ Import complete!${NC}"
echo -e "${BLUE}Connection string:${NC}"
echo -e "postgresql://$EC2_USER:$EC2_PASSWORD@$EC2_HOST:$EC2_PORT/$EC2_DB"