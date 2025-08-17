#!/bin/bash

# Simple ROS migration using complete-migration-to-ec2.sh approach
set -e

echo "=== MIGRATING ROS SCHEMA TO EC2 ==="

# Use the same approach as complete-migration-to-ec2.sh
cd /Users/subhajlimanond/dev/munbon2-backend

# Export ROS schema
echo "Exporting ROS schema from local..."
PGPASSWORD=postgres pg_dump -h localhost -p 5434 -U postgres \
    -d munbon_dev \
    -n ros \
    --clean \
    --if-exists \
    -f /tmp/ros_schema_complete.sql

# Also export gis.ros_water_demands
echo "Exporting GIS water demands..."
PGPASSWORD=postgres pg_dump -h localhost -p 5434 -U postgres \
    -d munbon_dev \
    -t gis.ros_water_demands \
    --clean \
    --if-exists \
    -f /tmp/gis_water_demands.sql

# Import to EC2 using the working method from complete-migration-to-ec2.sh
echo "Importing to EC2..."
EC2_HOST="${EC2_HOST:-43.208.201.191}"
EC2_PORT="5432"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

# Create schemas first
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev << EOF
CREATE SCHEMA IF NOT EXISTS ros;
CREATE SCHEMA IF NOT EXISTS gis;
EOF

# Import ROS schema
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev < /tmp/ros_schema_complete.sql

# Import GIS water demands
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev < /tmp/gis_water_demands.sql

# Verify
echo ""
echo "Verifying migration..."
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev << 'EOF'
SELECT 
    schemaname,
    tablename,
    n_live_tup as approx_rows
FROM pg_stat_user_tables
WHERE schemaname IN ('ros', 'gis')
ORDER BY schemaname, tablename;

\echo ''
\echo 'Exact counts for key tables:'
SELECT 'ros.plot_water_demand_weekly' as table_name, COUNT(*) FROM ros.plot_water_demand_weekly;
EOF

# Clean up
rm -f /tmp/ros_schema_complete.sql /tmp/gis_water_demands.sql

echo "✅ Migration complete!"