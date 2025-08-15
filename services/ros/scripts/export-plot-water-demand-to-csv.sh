#!/bin/bash

# Export plot water demand data to CSV files that can be opened in Excel

# Set database connection
export PGPASSWORD=postgres
DB_HOST=localhost
DB_PORT=5434
DB_NAME=munbon_dev
DB_USER=postgres

# Create output directory
OUTPUT_DIR="./output"
mkdir -p "$OUTPUT_DIR"

# Set timestamp for filenames
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "Exporting plot water demand data..."

# 1. Export main data (limited to first 100k rows for Excel compatibility)
echo "Exporting main water demand data..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\COPY (
    SELECT 
        plot_id,
        crop_type,
        crop_week,
        calendar_week,
        calendar_year,
        calculation_date,
        area_rai,
        monthly_eto,
        weekly_eto,
        kc_value,
        percolation,
        crop_water_demand_mm,
        crop_water_demand_m3,
        crop_water_demand_m3_per_rai,
        effective_rainfall_mm,
        net_water_demand_mm,
        net_water_demand_m3,
        net_water_demand_m3_per_rai,
        is_land_preparation
    FROM ros.plot_water_demand_weekly
    ORDER BY plot_id, crop_week
    LIMIT 100000
) TO '$OUTPUT_DIR/plot_water_demand_weekly_${TIMESTAMP}.csv' WITH CSV HEADER"

# 2. Export summary statistics
echo "Exporting summary statistics..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\COPY (
    SELECT 
        'Total Plots' as metric,
        COUNT(DISTINCT plot_id)::text as value
    FROM ros.plot_water_demand_weekly
    UNION ALL
    SELECT 
        'Total Records',
        COUNT(*)::text
    FROM ros.plot_water_demand_weekly
    UNION ALL
    SELECT 
        'Total Area (rai)',
        ROUND(SUM(DISTINCT area_rai), 2)::text
    FROM (SELECT plot_id, area_rai FROM ros.plot_water_demand_weekly GROUP BY plot_id, area_rai) t
    UNION ALL
    SELECT 
        'Total Crop Water Demand (m³)',
        ROUND(SUM(crop_water_demand_m3), 2)::text
    FROM ros.plot_water_demand_weekly
    UNION ALL
    SELECT 
        'Total Net Water Demand (m³)',
        ROUND(SUM(net_water_demand_m3), 2)::text
    FROM ros.plot_water_demand_weekly
    UNION ALL
    SELECT 
        'Avg Water Demand per Rai (m³/rai)',
        ROUND(AVG(crop_water_demand_m3_per_rai), 2)::text
    FROM ros.plot_water_demand_weekly
    WHERE crop_water_demand_m3_per_rai IS NOT NULL
) TO '$OUTPUT_DIR/plot_water_demand_summary_${TIMESTAMP}.csv' WITH CSV HEADER"

# 3. Export weekly aggregated data
echo "Exporting weekly summary..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\COPY (
    SELECT 
        calendar_year,
        calendar_week,
        COUNT(DISTINCT plot_id) as plot_count,
        ROUND(SUM(area_rai), 2) as total_area_rai,
        ROUND(SUM(crop_water_demand_m3), 2) as total_water_demand_m3,
        ROUND(SUM(net_water_demand_m3), 2) as total_net_demand_m3,
        ROUND(AVG(effective_rainfall_mm), 2) as avg_rainfall_mm,
        ROUND(AVG(crop_water_demand_m3_per_rai), 2) as avg_demand_per_rai
    FROM ros.plot_water_demand_weekly
    GROUP BY calendar_year, calendar_week
    ORDER BY calendar_year, calendar_week
) TO '$OUTPUT_DIR/plot_water_demand_weekly_summary_${TIMESTAMP}.csv' WITH CSV HEADER"

# 4. Export sample data (first 1000 rows for quick viewing)
echo "Exporting sample data..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\COPY (
    SELECT * FROM ros.plot_water_demand_weekly
    ORDER BY plot_id, crop_week
    LIMIT 1000
) TO '$OUTPUT_DIR/plot_water_demand_sample_${TIMESTAMP}.csv' WITH CSV HEADER"

echo "Export completed!"
echo "Files created in $OUTPUT_DIR:"
ls -la "$OUTPUT_DIR"/*${TIMESTAMP}*.csv

# Get record count
RECORD_COUNT=$(psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM ros.plot_water_demand_weekly")
echo ""
echo "Total records in table: $RECORD_COUNT"
echo "Note: Main export limited to 100,000 rows for Excel compatibility."
echo "For full data export, use database tools or split into multiple files."