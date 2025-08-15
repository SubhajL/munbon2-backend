#!/bin/bash

# Import ROS CSV data to EC2
set -e

# Use the same connection method as complete-migration-to-ec2.sh
EC2_HOST="43.209.22.250"
EC2_PORT="5432"
EC2_USER="postgres"
EC2_PASSWORD="P@ssw0rd123!"

echo "=== IMPORTING ROS DATA TO EC2 ==="

# Function to import CSV using psql stdin
import_table() {
    local table=$1
    local csv_file=$2
    
    echo "Importing $table..."
    
    # Get header and data separately
    header=$(head -1 "$csv_file")
    
    # Create temp file without problematic columns
    if [[ "$table" == "plots" ]]; then
        # Remove extra columns from plots CSV
        cut -d',' -f1-11 "$csv_file" > /tmp/temp_${table}.csv
    else
        cp "$csv_file" /tmp/temp_${table}.csv
    fi
    
    # Import using stdin redirection
    PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev << EOF
\COPY ros.$table FROM '/tmp/temp_${table}.csv' WITH CSV HEADER;
SELECT COUNT(*) as imported_count FROM ros.$table;
EOF
    
    rm -f /tmp/temp_${table}.csv
}

# Import tables in order (respecting foreign keys)
cd ros_export

# 1. Import plots first (parent table)
import_table "plots" "plots.csv"

# 2. Import dependent tables
import_table "plot_crop_schedule" "plot_crop_schedule.csv"
import_table "plot_water_demand_weekly" "plot_water_demand_weekly.csv"
import_table "plot_water_demand_seasonal" "plot_water_demand_seasonal.csv"
import_table "water_demand_calculations" "water_demand_calculations.csv"

# 3. Verify
echo ""
echo "Verification:"
PGPASSWORD=$EC2_PASSWORD psql -h $EC2_HOST -p $EC2_PORT -U $EC2_USER -d munbon_dev << 'EOF'
SELECT 
    'ros.plots' as table_name, COUNT(*) as records FROM ros.plots
UNION ALL
SELECT 'ros.plot_water_demand_weekly', COUNT(*) FROM ros.plot_water_demand_weekly
UNION ALL
SELECT 'ros.plot_water_demand_seasonal', COUNT(*) FROM ros.plot_water_demand_seasonal
ORDER BY table_name;
EOF

echo "✅ Import complete!"