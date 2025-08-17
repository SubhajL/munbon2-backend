#!/bin/bash

# Final ROS import script
set -e

echo "=== IMPORTING ROS DATA TO EC2 ==="

# Step 1: Export from local with compatible pg_dump
echo "Step 1: Creating compatible export..."

# Use COPY TO STDOUT to avoid file permission issues
PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d munbon_dev << 'EOF' > /tmp/ros_export.sql
-- Export schema structure
\echo 'SET search_path TO ros, public;'
\echo ''

-- Export plots data
\echo 'TRUNCATE TABLE ros.plots CASCADE;'
\echo 'COPY ros.plots (plot_id, plot_code, area_rai, geometry, parent_section_id, parent_zone_id, aos_station, province, created_at, updated_at) FROM stdin;'
COPY (SELECT plot_id, plot_code, area_rai, geometry, parent_section_id, parent_zone_id, aos_station, province, created_at, updated_at FROM ros.plots ORDER BY id) TO STDOUT;
\echo '\.'
\echo ''

-- Export plot_crop_schedule data
\echo 'COPY ros.plot_crop_schedule FROM stdin;'
COPY ros.plot_crop_schedule TO STDOUT;
\echo '\.'
\echo ''

-- Export plot_water_demand_weekly data
\echo 'COPY ros.plot_water_demand_weekly FROM stdin;'
COPY ros.plot_water_demand_weekly TO STDOUT;
\echo '\.'
\echo ''

-- Export plot_water_demand_seasonal data
\echo 'COPY ros.plot_water_demand_seasonal FROM stdin;'
COPY ros.plot_water_demand_seasonal TO STDOUT;
\echo '\.'
\echo ''

-- Export water_demand_calculations data
\echo 'COPY ros.water_demand_calculations FROM stdin;'
COPY ros.water_demand_calculations TO STDOUT;
\echo '\.'
EOF

# Step 2: Import to EC2
echo -e "\nStep 2: Importing to EC2..."

EC2_HOST="${EC2_HOST:-43.208.201.191}"
EC2_PORT="5432"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev < /tmp/ros_export.sql

# Step 3: Also migrate gis.ros_water_demands
echo -e "\nStep 3: Migrating GIS water demands..."

# Export GIS data
PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d munbon_dev << 'EOF' > /tmp/gis_export.sql
\echo 'CREATE SCHEMA IF NOT EXISTS gis;'
\echo 'CREATE TABLE IF NOT EXISTS gis.ros_water_demands ('
\echo '    id SERIAL PRIMARY KEY,'
\echo '    plot_id VARCHAR(255),'
\echo '    zone_name VARCHAR(255),'
\echo '    section_name VARCHAR(255),'
\echo '    plot_code VARCHAR(255),'
\echo '    area_rai DECIMAL,'
\echo '    crop_type VARCHAR(100),'
\echo '    planting_date DATE,'
\echo '    crop_age_days INTEGER,'
\echo '    weekly_demand_m3 DECIMAL,'
\echo '    monthly_demand_m3 DECIMAL,'
\echo '    irrigation_efficiency DECIMAL,'
\echo '    calculation_date TIMESTAMP,'
\echo '    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,'
\echo '    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
\echo ');'
\echo 'TRUNCATE TABLE gis.ros_water_demands;'
\echo 'COPY gis.ros_water_demands FROM stdin;'
COPY gis.ros_water_demands TO STDOUT;
\echo '\.'
EOF

# Import GIS data
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev < /tmp/gis_export.sql

# Step 4: Verify
echo -e "\nStep 4: Verifying import..."
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev << 'EOF'
SELECT 
    schemaname || '.' || tablename as table_name,
    to_char(n_live_tup, 'FM999,999') as records
FROM pg_stat_user_tables
WHERE schemaname IN ('ros', 'gis')
  AND tablename IN ('plots', 'plot_crop_schedule', 'plot_water_demand_weekly', 
                    'plot_water_demand_seasonal', 'water_demand_calculations', 
                    'ros_water_demands')
ORDER BY schemaname, tablename;
EOF

# Clean up
rm -f /tmp/ros_export.sql /tmp/gis_export.sql

echo -e "\n✅ Import complete!"
echo "EC2 Connection: postgresql://postgres:PASSWORD@${EC2_HOST:-43.208.201.191}:5432/munbon_dev"