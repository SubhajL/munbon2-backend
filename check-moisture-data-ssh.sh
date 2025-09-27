#!/bin/bash

# EC2 instance details
EC2_HOST="43.208.201.191"
EC2_USER="ubuntu"
SSH_KEY_PATH="$HOME/dev/th-lab01.pem"  # Update this to your SSH key path

echo "=== Checking Moisture Data in EC2 Database via SSH ==="
echo "Timestamp: $(date)"
echo ""

# SSH command to run PostgreSQL queries
ssh_query() {
    local query=$1
    ssh -o StrictHostKeyChecking=no -i ${SSH_KEY_PATH} ${EC2_USER}@${EC2_HOST} \
        "sudo -u postgres psql -d sensor_data -c \"$query\""
}

echo "1. Checking if moisture_readings table exists:"
ssh_query "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'moisture_readings');"

echo ""
echo "2. Counting total moisture readings:"
ssh_query "SELECT COUNT(*) as total_readings FROM moisture_readings;"

echo ""
echo "3. Looking for test data I sent (sensor IDs containing 'test'):"
ssh_query "SELECT sensor_id, time, moisture_surface_pct, moisture_deep_pct, location_lat, location_lng 
           FROM moisture_readings 
           WHERE sensor_id LIKE '%test%' 
           ORDER BY time DESC 
           LIMIT 10;"

echo ""
echo "4. Latest 10 moisture readings (any sensor):"
ssh_query "SELECT sensor_id, time, moisture_surface_pct as surface, moisture_deep_pct as deep, 
           temp_surface_c as temp_surf, temp_deep_c as temp_deep
           FROM moisture_readings 
           ORDER BY time DESC 
           LIMIT 10;"

echo ""
echo "5. Moisture readings from last hour:"
ssh_query "SELECT sensor_id, COUNT(*) as reading_count, 
           MAX(time) as last_reading, 
           AVG(moisture_surface_pct) as avg_surface_moisture
           FROM moisture_readings 
           WHERE time > NOW() - INTERVAL '1 hour' 
           GROUP BY sensor_id
           ORDER BY last_reading DESC;"

echo ""
echo "6. Checking for specific test gateway IDs:"
for gateway_id in "test-moisture-001" "curl-test-001" "check-test-001" "api-test-001"; do
    echo "Checking for gateway: $gateway_id"
    ssh_query "SELECT COUNT(*) as count FROM moisture_readings WHERE sensor_id LIKE '%$gateway_id%';"
done