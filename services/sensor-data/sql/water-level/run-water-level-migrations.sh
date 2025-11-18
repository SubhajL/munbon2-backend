#!/bin/bash

# Run water level smoothing SQL migrations
# This script executes the SQL files in order to set up water level smoothing infrastructure

# Set working directory
cd "$(dirname "$0")"

# Database connection parameters
DB_HOST="${TIMESCALE_HOST:-43.208.201.191}"
DB_PORT="${TIMESCALE_PORT:-5432}"
DB_NAME="${TIMESCALE_DB:-sensor_data}"
DB_USER="${TIMESCALE_USER:-postgres}"
DB_PASSWORD="${TIMESCALE_PASSWORD:-P@ssw0rd123!}"

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to run SQL file
run_sql() {
    local sql_file=$1
    local description=$2

    echo -e "${YELLOW}Running: ${description}${NC}"
    echo "File: ${sql_file}"

    if [ ! -f "${sql_file}" ]; then
        echo -e "${RED}Error: SQL file not found: ${sql_file}${NC}"
        return 1
    fi

    # Try connection string method first
    if psql "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=disable" -f "${sql_file}" 2>&1; then
        echo -e "${GREEN}✓ Success: ${description}${NC}\n"
        return 0
    else
        # Fallback to PGPASSWORD method
        if PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -f "${sql_file}" 2>&1; then
            echo -e "${GREEN}✓ Success: ${description}${NC}\n"
            return 0
        else
            echo -e "${RED}✗ Failed: ${description}${NC}\n"
            return 1
        fi
    fi
}

# Function to run query and return result
run_query() {
    local query=$1
    psql "postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=disable" -t -c "${query}" 2>/dev/null
}

# Main execution
echo -e "${YELLOW}=== Water Level Smoothing Infrastructure Setup ===${NC}\n"

# Check database connection
echo -e "${YELLOW}Testing database connection...${NC}"
if run_query "SELECT 1" > /dev/null; then
    echo -e "${GREEN}✓ Database connection successful${NC}\n"
else
    echo -e "${RED}✗ Cannot connect to database${NC}"
    exit 1
fi

# Run migrations based on command argument
case "$1" in
    "create-table")
        run_sql "01_create_smoothed_table.sql" "Create smoothed water level table"
        ;;
    "profile-raw")
        run_sql "02_profile_quality_raw.sql" "Profile raw water level quality"
        ;;
    "backfill")
        run_sql "04_backfill_smoothing_14d.sql" "Backfill 14 days of smoothed data"
        ;;
    "profile-smoothed")
        run_sql "03_profile_quality_smoothed.sql" "Profile smoothed water level quality"
        ;;
    "add-params")
        run_sql "06_create_smoothing_params.sql" "Add water level smoothing parameters"
        ;;
    "create-trigger")
        run_sql "07_realtime_smoothing_fn_and_trigger.sql" "Create real-time smoothing trigger"
        ;;
    "all")
        # Run all migrations in order
        run_sql "01_create_smoothed_table.sql" "Create smoothed water level table"
        run_sql "02_profile_quality_raw.sql" "Profile raw water level quality"
        run_sql "06_create_smoothing_params.sql" "Add water level smoothing parameters"
        run_sql "04_backfill_smoothing_14d.sql" "Backfill 14 days of smoothed data"
        run_sql "03_profile_quality_smoothed.sql" "Profile smoothed water level quality"
        run_sql "07_realtime_smoothing_fn_and_trigger.sql" "Create real-time smoothing trigger"
        ;;
    "verify")
        # Verify installation
        echo -e "${YELLOW}Verifying water level smoothing infrastructure...${NC}\n"

        # Check if table exists
        if run_query "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'smoothed_water_level_readings')" | grep -q 't'; then
            echo -e "${GREEN}✓ Table 'smoothed_water_level_readings' exists${NC}"
        else
            echo -e "${RED}✗ Table 'smoothed_water_level_readings' not found${NC}"
        fi

        # Check row count
        count=$(run_query "SELECT COUNT(*) FROM smoothed_water_level_readings")
        echo -e "${YELLOW}  Smoothed data rows: ${count}${NC}"

        # Check if trigger exists
        if run_query "SELECT EXISTS (SELECT 1 FROM information_schema.triggers WHERE trigger_name = 'trigger_smooth_water_level')" | grep -q 't'; then
            echo -e "${GREEN}✓ Real-time smoothing trigger exists${NC}"
        else
            echo -e "${YELLOW}! Real-time smoothing trigger not yet created${NC}"
        fi

        # Check smoothing params
        param_count=$(run_query "SELECT COUNT(*) FROM smoothing_params WHERE sensor_id LIKE 'AWD-%'")
        echo -e "${YELLOW}  Water level sensor parameters: ${param_count}${NC}"
        ;;
    *)
        echo "Usage: $0 {create-table|profile-raw|add-params|backfill|profile-smoothed|create-trigger|all|verify}"
        echo ""
        echo "Commands:"
        echo "  create-table     - Create smoothed_water_level_readings table"
        echo "  profile-raw      - Analyze raw water level data quality"
        echo "  add-params       - Add smoothing parameters for water level sensors"
        echo "  backfill         - Backfill 14 days of smoothed data"
        echo "  profile-smoothed - Analyze smoothed data quality"
        echo "  create-trigger   - Create real-time smoothing trigger"
        echo "  all              - Run all migrations in order"
        echo "  verify           - Verify installation status"
        exit 1
        ;;
esac

echo -e "${GREEN}Done!${NC}"