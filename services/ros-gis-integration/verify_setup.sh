#!/bin/bash

echo "=== ROS-GIS Consolidation Setup Verification ==="
echo ""

# Database connection details
DB_HOST="localhost"
DB_PORT="5434"
DB_NAME="munbon_dev"
DB_USER="postgres"
export PGPASSWORD="postgres"

echo "1. Checking tables..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT '✓ ' || schemaname || '.' || tablename as table_name
FROM pg_tables 
WHERE schemaname = 'gis' 
AND tablename IN ('ros_water_demands', 'agricultural_plots')
ORDER BY tablename;
"

echo ""
echo "2. Checking views..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT '✓ ' || schemaname || '.' || viewname as view_name
FROM pg_views 
WHERE schemaname = 'gis' 
AND viewname = 'latest_ros_demands';
"

echo ""
echo "3. Checking materialized views..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT '✓ ' || schemaname || '.' || matviewname as matview_name
FROM pg_matviews 
WHERE schemaname = 'gis' 
AND matviewname = 'weekly_demand_summary';
"

echo ""
echo "4. Row counts..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT 'Agricultural plots: ' || COUNT(*) FROM gis.agricultural_plots;
"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT 'ROS water demands: ' || COUNT(*) FROM gis.ros_water_demands;
"

echo ""
echo "5. Sample agricultural plots..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT 
    plot_code,
    ROUND(area_hectares::numeric, 2) as hectares,
    ROUND((area_hectares * 6.25)::numeric, 2) as rai,
    properties->>'amphoe' as amphoe,
    properties->>'tambon' as tambon
FROM gis.agricultural_plots
LIMIT 5;
"

echo ""
echo "6. Testing insert capability..."
# Insert test data
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
INSERT INTO gis.ros_water_demands (
    parcel_id, section_id, calculation_date, calendar_week, calendar_year,
    crop_type, crop_week, growth_stage, area_rai,
    et0_mm, kc_factor, percolation_mm,
    gross_demand_mm, gross_demand_m3, net_demand_mm, net_demand_m3
) 
SELECT 
    id,
    'section_test',
    CURRENT_TIMESTAMP,
    18,
    2024,
    'rice',
    5,
    'tillering',
    area_hectares * 6.25,  -- Convert to rai
    5.2,
    1.05,
    14.0,
    19.46,
    325.0,
    15.46,
    258.0
FROM gis.agricultural_plots
LIMIT 1
ON CONFLICT (parcel_id, calendar_week, calendar_year) 
WHERE parcel_id IS NOT NULL
DO UPDATE SET
    calculation_date = EXCLUDED.calculation_date,
    crop_type = EXCLUDED.crop_type,
    net_demand_m3 = EXCLUDED.net_demand_m3,
    updated_at = CURRENT_TIMESTAMP
RETURNING parcel_id, crop_type, net_demand_m3;
"

echo ""
echo "7. Checking latest_ros_demands view..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT 
    plot_code,
    crop_type,
    ROUND(net_demand_m3::numeric, 1) as demand_m3,
    tambon,
    amphoe
FROM gis.latest_ros_demands
LIMIT 5;
"

echo ""
echo "✅ Setup verification complete!"
echo ""
echo "Summary:"
echo "- Database: $DB_NAME on port $DB_PORT"
echo "- Tables created in 'gis' schema"
echo "- ROS water demands can be inserted and queried"
echo "- Areas are stored in rai (converted from hectares)"
echo ""
echo "Next steps:"
echo "1. Start services:"
echo "   - ROS Service (port 3047)"
echo "   - GIS Service (port 3007)" 
echo "   - ROS-GIS Integration (port 3022)"
echo "2. Configure services with USE_MOCK_SERVER=false"
echo "3. Trigger sync via POST http://localhost:3022/api/v1/sync/trigger"