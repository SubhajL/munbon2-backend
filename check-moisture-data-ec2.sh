#!/bin/bash

# EC2 instance details
EC2_HOST="43.208.201.191"

# Function to run PostgreSQL query on EC2
run_query() {
    local query=$1
    ssh -o StrictHostKeyChecking=no ubuntu@${EC2_HOST} "sudo -u postgres psql -d sensor_data -c \"$query\""
}

echo "=== Checking Moisture Sensor Data on EC2 ==="
echo "Timestamp: $(date)"
echo ""

# Check if moisture_readings table exists
echo "1. Checking if moisture_readings table exists:"
run_query "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'moisture_readings');"

echo ""
echo "2. Counting total moisture readings:"
run_query "SELECT COUNT(*) as total_readings FROM moisture_readings;"

echo ""
echo "3. Latest 10 moisture readings:"
run_query "SELECT sensor_id, time, moisture_surface_pct, moisture_deep_pct, location_lat, location_lng FROM moisture_readings ORDER BY time DESC LIMIT 10;"

echo ""
echo "4. Moisture readings from last 24 hours:"
run_query "SELECT sensor_id, COUNT(*) as reading_count, MAX(time) as last_reading FROM moisture_readings WHERE time > NOW() - INTERVAL '24 hours' GROUP BY sensor_id;"

echo ""
echo "5. Unique moisture sensor IDs:"
run_query "SELECT DISTINCT sensor_id FROM moisture_readings ORDER BY sensor_id;"

echo ""
echo "6. Checking sensor_registry for moisture sensors:"
run_query "SELECT sensor_id, sensor_type, name, last_seen FROM sensor_registry WHERE sensor_type = 'moisture' ORDER BY last_seen DESC LIMIT 10;"