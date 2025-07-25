#!/bin/bash

# Script to execute ROS water demands migration
# This creates the necessary tables and views for ROS-GIS consolidation

echo "Running ROS water demands migration..."
echo "=================================="

# Database connection details
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5434}"  # Default to local munbon_dev
DB_NAME="${DB_NAME:-munbon_dev}"
DB_USER="${DB_USER:-postgres}"
DB_SCHEMA="${DB_SCHEMA:-gis}"

# Check if migration file exists
MIGRATION_FILE="../migrations/004_add_ros_water_demands.sql"

if [ ! -f "$MIGRATION_FILE" ]; then
    echo "Error: Migration file not found at $MIGRATION_FILE"
    exit 1
fi

echo "Database: $DB_NAME"
echo "Schema: $DB_SCHEMA"
echo "Migration file: $MIGRATION_FILE"
echo ""

# Run the migration
echo "Executing migration..."
PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$MIGRATION_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Migration completed successfully!"
    echo ""
    echo "Created:"
    echo "  - Table: gis.ros_water_demands"
    echo "  - View: gis.latest_ros_demands"
    echo "  - Materialized View: gis.weekly_demand_summary"
    echo "  - Indexes and triggers"
else
    echo ""
    echo "❌ Migration failed!"
    exit 1
fi

# Verify the tables were created
echo ""
echo "Verifying tables..."
PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE schemaname = '$DB_SCHEMA' 
AND tablename IN ('ros_water_demands')
ORDER BY tablename;
"

echo ""
echo "Verifying views..."
PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT 
    schemaname,
    viewname,
    viewowner
FROM pg_views 
WHERE schemaname = '$DB_SCHEMA' 
AND viewname IN ('latest_ros_demands')
ORDER BY viewname;
"

echo ""
echo "Verifying materialized views..."
PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT 
    schemaname,
    matviewname,
    matviewowner
FROM pg_matviews 
WHERE schemaname = '$DB_SCHEMA' 
AND matviewname IN ('weekly_demand_summary')
ORDER BY matviewname;
"

echo ""
echo "Migration verification complete!"
echo ""
echo "Next steps:"
echo "1. Restart the GIS service to load new routes"
echo "2. Run the ROS-GIS integration service with USE_MOCK_SERVER=false"
echo "3. Trigger a sync using: POST http://localhost:3022/api/v1/sync/trigger"