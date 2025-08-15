#!/bin/bash

# Export ROS tables to CSV files
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Local database
export PGPASSWORD="postgres"
DB_HOST="localhost"
DB_PORT="5434"
DB_NAME="munbon_dev"
DB_USER="postgres"

# Create export directory
EXPORT_DIR="./ros_export"
mkdir -p "$EXPORT_DIR"

echo -e "${BLUE}=== EXPORTING ROS TABLES TO CSV ===${NC}"

# Export plot_water_demand_weekly
echo -e "${YELLOW}Exporting plot_water_demand_weekly...${NC}"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\COPY ros.plot_water_demand_weekly TO '$EXPORT_DIR/plot_water_demand_weekly.csv' WITH CSV HEADER"

# Export other tables
echo -e "${YELLOW}Exporting plot_water_demand_seasonal...${NC}"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\COPY ros.plot_water_demand_seasonal TO '$EXPORT_DIR/plot_water_demand_seasonal.csv' WITH CSV HEADER"

echo -e "${YELLOW}Exporting water_demand_calculations...${NC}"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\COPY ros.water_demand_calculations TO '$EXPORT_DIR/water_demand_calculations.csv' WITH CSV HEADER"

echo -e "${YELLOW}Exporting plots...${NC}"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\COPY ros.plots TO '$EXPORT_DIR/plots.csv' WITH CSV HEADER"

echo -e "${YELLOW}Exporting plot_crop_schedule...${NC}"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\COPY ros.plot_crop_schedule TO '$EXPORT_DIR/plot_crop_schedule.csv' WITH CSV HEADER"

# Check if gis.ros_water_demands exists
if psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "SELECT 1 FROM information_schema.tables WHERE table_schema='gis' AND table_name='ros_water_demands';" | grep -q 1; then
    echo -e "${YELLOW}Exporting gis.ros_water_demands...${NC}"
    psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "\COPY gis.ros_water_demands TO '$EXPORT_DIR/gis_ros_water_demands.csv' WITH CSV HEADER"
fi

# Also export table DDL
echo -e "\n${BLUE}Exporting table structures...${NC}"
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "
SELECT 
    'CREATE TABLE ros.' || table_name || ' (' || E'\n' ||
    string_agg(
        '    ' || column_name || ' ' || 
        CASE 
            WHEN data_type = 'character varying' THEN 'VARCHAR(' || character_maximum_length || ')'
            WHEN data_type = 'numeric' THEN 'DECIMAL(' || numeric_precision || ',' || numeric_scale || ')'
            WHEN data_type = 'timestamp without time zone' THEN 'TIMESTAMP'
            ELSE data_type
        END ||
        CASE WHEN is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END ||
        CASE WHEN column_default IS NOT NULL THEN ' DEFAULT ' || column_default ELSE '' END,
        E',\n' ORDER BY ordinal_position
    ) || E'\n);'
FROM information_schema.columns
WHERE table_schema = 'ros'
GROUP BY table_name
ORDER BY table_name;" > "$EXPORT_DIR/ros_tables_ddl.sql"

# List exported files
echo -e "\n${GREEN}Export complete! Files created:${NC}"
ls -lh "$EXPORT_DIR"/*.csv
echo -e "\n${BLUE}Table structure saved to: $EXPORT_DIR/ros_tables_ddl.sql${NC}"

# Show record counts
echo -e "\n${YELLOW}Record counts:${NC}"
for file in "$EXPORT_DIR"/*.csv; do
    if [[ -f "$file" ]]; then
        count=$(($(wc -l < "$file") - 1))  # Subtract header
        basename=$(basename "$file")
        echo -e "$basename: $count records"
    fi
done