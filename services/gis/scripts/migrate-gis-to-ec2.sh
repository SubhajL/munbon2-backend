#!/bin/bash

echo "=== GIS Data Migration: Local to EC2 ==="
echo "======================================="

# Configuration
LOCAL_HOST="localhost"
LOCAL_PORT="5434"
LOCAL_USER="postgres"
LOCAL_PASS="postgres"
LOCAL_DB="munbon_dev"

EC2_HOST="${EC2_HOST:-43.208.201.191}"
EC2_PORT="5432"
EC2_USER="postgres"
EC2_PASS="P@ssw0rd123!"  # Update this!
EC2_DB="munbon_dev"

SSH_KEY="$HOME/dev/th-lab01.pem"
DUMP_FILE="gis_schema_$(date +%Y%m%d_%H%M%S).dump"

echo "Step 1: Checking local data..."
echo "------------------------------"
PGPASSWORD=$LOCAL_PASS psql -h $LOCAL_HOST -p $LOCAL_PORT -U $LOCAL_USER -d $LOCAL_DB -c "
SELECT 
    table_name,
    pg_size_pretty(pg_total_relation_size('gis.'||table_name)) as size,
    (SELECT COUNT(*) FROM gis.agricultural_plots WHERE table_name='agricultural_plots') as row_count
FROM information_schema.tables 
WHERE table_schema = 'gis' 
AND table_type = 'BASE TABLE'
AND table_name IN ('agricultural_plots', 'irrigation_zones', 'shape_file_uploads')
ORDER BY pg_total_relation_size('gis.'||table_name) DESC;"

echo ""
echo "Step 2: Creating database dump..."
echo "--------------------------------"
PGPASSWORD=$LOCAL_PASS pg_dump -h $LOCAL_HOST -p $LOCAL_PORT -U $LOCAL_USER \
    -d $LOCAL_DB -n gis -Fc -v -f $DUMP_FILE

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create database dump!"
    exit 1
fi

echo "Dump created: $DUMP_FILE ($(du -h $DUMP_FILE | cut -f1))"

echo ""
echo "Step 3: Transferring to EC2..."
echo "-----------------------------"
scp -i $SSH_KEY $DUMP_FILE ubuntu@$EC2_HOST:/tmp/

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to transfer dump file!"
    exit 1
fi

echo ""
echo "Step 4: Preparing EC2 database..."
echo "---------------------------------"
ssh -i $SSH_KEY ubuntu@$EC2_HOST << EOF
    echo "Checking PostGIS extension..."
    PGPASSWORD='$EC2_PASS' psql -h localhost -U $EC2_USER -d $EC2_DB -c "CREATE EXTENSION IF NOT EXISTS postgis;"
    
    echo "Creating gis schema if not exists..."
    PGPASSWORD='$EC2_PASS' psql -h localhost -U $EC2_USER -d $EC2_DB -c "CREATE SCHEMA IF NOT EXISTS gis;"
EOF

echo ""
echo "Step 5: Importing data to EC2..."
echo "--------------------------------"
echo "This may take a while for large datasets..."
ssh -i $SSH_KEY ubuntu@$EC2_HOST "PGPASSWORD='$EC2_PASS' pg_restore -h localhost -U $EC2_USER -d $EC2_DB -n gis --if-exists -c -v /tmp/$DUMP_FILE"

echo ""
echo "Step 6: Creating spatial indexes..."
echo "----------------------------------"
ssh -i $SSH_KEY ubuntu@$EC2_HOST << EOF
    PGPASSWORD='$EC2_PASS' psql -h localhost -U $EC2_USER -d $EC2_DB << SQL
        -- Spatial indexes for agricultural plots
        CREATE INDEX IF NOT EXISTS idx_agricultural_plots_boundary 
        ON gis.agricultural_plots USING GIST (boundary);
        
        -- Spatial indexes for irrigation zones
        CREATE INDEX IF NOT EXISTS idx_irrigation_zones_boundary 
        ON gis.irrigation_zones USING GIST (boundary);
        
        -- Additional indexes
        CREATE INDEX IF NOT EXISTS idx_agricultural_plots_plot_code 
        ON gis.agricultural_plots (plot_code);
        
        CREATE INDEX IF NOT EXISTS idx_irrigation_zones_zone_code 
        ON gis.irrigation_zones (zone_code);
SQL
EOF

echo ""
echo "Step 7: Verifying migration..."
echo "------------------------------"
ssh -i $SSH_KEY ubuntu@$EC2_HOST << EOF
    PGPASSWORD='$EC2_PASS' psql -h localhost -U $EC2_USER -d $EC2_DB -c "
        SELECT 
            'agricultural_plots' as table_name, 
            COUNT(*) as row_count,
            pg_size_pretty(pg_total_relation_size('gis.agricultural_plots')) as size
        FROM gis.agricultural_plots
        UNION ALL
        SELECT 
            'irrigation_zones' as table_name, 
            COUNT(*) as row_count,
            pg_size_pretty(pg_total_relation_size('gis.irrigation_zones')) as size
        FROM gis.irrigation_zones
        UNION ALL
        SELECT 
            'shape_file_uploads' as table_name, 
            COUNT(*) as row_count,
            pg_size_pretty(pg_total_relation_size('gis.shape_file_uploads')) as size
        FROM gis.shape_file_uploads;"
EOF

echo ""
echo "Step 8: Cleanup..."
echo "-----------------"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "rm -f /tmp/$DUMP_FILE"
rm -f $DUMP_FILE

echo ""
echo "=== Migration Complete! ==="
echo ""
echo "Next steps:"
echo "1. Verify the GIS service can connect to EC2 database"
echo "2. Test shapefile upload functionality"
echo "3. Check integration with other services"
echo ""
echo "Current GIS service configuration:"
grep DATABASE_URL ../.env | head -1