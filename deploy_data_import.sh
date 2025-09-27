#!/bin/bash

echo "=== Deploying and Running Data Import on EC2 ==="
echo "Date: $(date)"

# Configuration
EC2_IP="43.208.201.191"
SSH_KEY="~/dev/th-lab01.pem"
REMOTE_PATH="/home/ubuntu/munbon-data-import"

# Create remote directory
echo "1. Creating remote directory..."
ssh -i $SSH_KEY ubuntu@$EC2_IP "mkdir -p $REMOTE_PATH"

# Copy files to EC2
echo "2. Copying files to EC2..."
scp -i $SSH_KEY -r data_ridplan data_water_level ubuntu@$EC2_IP:$REMOTE_PATH/
scp -i $SSH_KEY import_ridplan_water_level_data.py ubuntu@$EC2_IP:$REMOTE_PATH/

# Run the import script on EC2
echo "3. Running import on EC2..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
cd /home/ubuntu/munbon-data-import

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install required Python packages
echo "Installing required packages..."
pip install geopandas psycopg2-binary pandas numpy shapely

# Set database password
export POSTGRES_PASSWORD="YourSecurePasswordHere123!"

# Run the import script
echo "Running import script..."
python import_ridplan_water_level_data.py

# Check results
echo ""
echo "=== Checking imported data ==="
docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -c "
SELECT COUNT(*) as new_parcels FROM gis.parcels 
WHERE data->>'type' = 'rid_ms_parcel' 
AND data->>'source' = 'excel_rice_20250810_merge';"

docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -c "
SELECT COUNT(*) as new_water_levels FROM ros_gis.manual_water_level_readings 
WHERE geopackage_source = 'data_water_level.gpkg' 
AND DATE(created_at) = CURRENT_DATE;"

echo ""
echo "=== Sample imported parcel ==="
docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -c "
SELECT id, 
       data->'parcel_data'->>'parcel_seq' as parcel_seq,
       data->'parcel_data'->>'zone_area' as zone_area,
       data->'parcel_data'->>'area_rai' as area_rai,
       data->'parcel_data'->>'plant_id' as plant_id
FROM gis.parcels 
WHERE data->>'type' = 'rid_ms_parcel' 
ORDER BY id DESC LIMIT 3;"

echo ""
echo "=== Sample imported water levels ==="
docker exec postgres_timescale_postgis psql -U postgres -d munbon_dev -c "
SELECT reading_id, plot_id, water_level_m, reading_date, notes 
FROM ros_gis.manual_water_level_readings 
WHERE geopackage_source = 'data_water_level.gpkg' 
ORDER BY created_at DESC LIMIT 5;"
EOF

echo ""
echo "=== Import process completed ==="