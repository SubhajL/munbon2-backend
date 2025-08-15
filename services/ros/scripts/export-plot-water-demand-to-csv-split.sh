#!/bin/bash

# Export plot water demand data to CSV files split for Excel compatibility

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

echo "Exporting plot water demand data (split into 2 files for Excel)..."

# Get total record count
TOTAL_RECORDS=$(psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM ros.plot_water_demand_weekly")
echo "Total records: $TOTAL_RECORDS"

# 1. Export first half (Part 1)
echo "Exporting Part 1 (first 105,483 records)..."
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
    LIMIT 105483
) TO '$OUTPUT_DIR/plot_water_demand_weekly_part1_${TIMESTAMP}.csv' WITH CSV HEADER"

# 2. Export second half (Part 2)
echo "Exporting Part 2 (remaining 105,483 records)..."
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
    OFFSET 105483
) TO '$OUTPUT_DIR/plot_water_demand_weekly_part2_${TIMESTAMP}.csv' WITH CSV HEADER"

# 3. Export summary statistics
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
        TO_CHAR(SUM(crop_water_demand_m3), 'FM999,999,999,999.99')
    FROM ros.plot_water_demand_weekly
    UNION ALL
    SELECT 
        'Total Net Water Demand (m³)',
        TO_CHAR(SUM(net_water_demand_m3), 'FM999,999,999,999.99')
    FROM ros.plot_water_demand_weekly
    UNION ALL
    SELECT 
        'Avg Water Demand per Rai (m³/rai)',
        ROUND(AVG(crop_water_demand_m3_per_rai), 2)::text
    FROM ros.plot_water_demand_weekly
    WHERE crop_water_demand_m3_per_rai IS NOT NULL
) TO '$OUTPUT_DIR/plot_water_demand_summary_${TIMESTAMP}.csv' WITH CSV HEADER"

# 4. Export weekly aggregated data
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

# 5. Create a plot index file to help identify which plots are in which file
echo "Creating plot index..."
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\COPY (
    WITH plot_order AS (
        SELECT DISTINCT plot_id,
               ROW_NUMBER() OVER (ORDER BY plot_id) as row_num
        FROM ros.plot_water_demand_weekly
    )
    SELECT 
        plot_id,
        CASE 
            WHEN row_num <= (SELECT COUNT(DISTINCT plot_id)/2 FROM ros.plot_water_demand_weekly) 
            THEN 'Part 1'
            ELSE 'Part 2'
        END as file_part
    FROM plot_order
    ORDER BY plot_id
) TO '$OUTPUT_DIR/plot_index_${TIMESTAMP}.csv' WITH CSV HEADER"

echo ""
echo "Export completed!"
echo "Files created in $OUTPUT_DIR:"
ls -la "$OUTPUT_DIR"/*${TIMESTAMP}*.csv | awk '{print $9, "(" $5 " bytes)"}'

# Show file statistics
echo ""
echo "File Statistics:"
echo "----------------"
PART1_COUNT=$(wc -l < "$OUTPUT_DIR/plot_water_demand_weekly_part1_${TIMESTAMP}.csv")
PART2_COUNT=$(wc -l < "$OUTPUT_DIR/plot_water_demand_weekly_part2_${TIMESTAMP}.csv")
echo "Part 1: $((PART1_COUNT - 1)) records (excluding header)"
echo "Part 2: $((PART2_COUNT - 1)) records (excluding header)"
echo "Total: $((PART1_COUNT + PART2_COUNT - 2)) records"
echo ""
echo "All files can be opened directly in Excel!"