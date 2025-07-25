#!/bin/bash

# Export munbon_dev database (port 5434) to CSV files

echo "=== Exporting munbon_dev database (port 5434) ==="
echo ""

# Create directories for exports
mkdir -p gis_data
mkdir -p ros_data

# Export GIS schema tables
echo "Exporting GIS schema tables..."

# List all tables in gis schema
docker exec munbon-postgres psql -U postgres -d munbon_dev -t -c "
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'gis' 
AND table_type = 'BASE TABLE'
ORDER BY table_name;" | while read -r table; do
    if [ ! -z "$table" ]; then
        table=$(echo $table | xargs)  # trim whitespace
        echo -n "Exporting gis.$table... "
        
        # Export to CSV
        docker exec munbon-postgres psql -U postgres -d munbon_dev -c "\COPY gis.$table TO STDOUT WITH CSV HEADER" > "gis_data/$table.csv"
        
        # Count rows
        rows=$(wc -l < "gis_data/$table.csv")
        echo "$rows lines"
    fi
done

# Export ROS schema tables
echo ""
echo "Exporting ROS schema tables..."

# List all tables in ros schema
docker exec munbon-postgres psql -U postgres -d munbon_dev -t -c "
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'ros' 
AND table_type = 'BASE TABLE'
ORDER BY table_name;" | while read -r table; do
    if [ ! -z "$table" ]; then
        table=$(echo $table | xargs)  # trim whitespace
        echo -n "Exporting ros.$table... "
        
        # Export to CSV
        docker exec munbon-postgres psql -U postgres -d munbon_dev -c "\COPY ros.$table TO STDOUT WITH CSV HEADER" > "ros_data/$table.csv"
        
        # Count rows
        rows=$(wc -l < "ros_data/$table.csv")
        echo "$rows lines"
    fi
done

echo ""
echo "Export complete!"
echo ""
echo "Summary:"
echo "- GIS data exported to: ./gis_data/"
echo "- ROS data exported to: ./ros_data/"

# Show file sizes
echo ""
echo "GIS data files:"
ls -lh gis_data/*.csv 2>/dev/null || echo "  No files found"

echo ""
echo "ROS data files:"
ls -lh ros_data/*.csv 2>/dev/null || echo "  No files found"