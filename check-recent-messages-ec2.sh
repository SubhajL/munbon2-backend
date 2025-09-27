#!/bin/bash

echo "=== Checking Last 9 Messages from Past 15 Days in EC2 Database ==="
echo "Date: $(date)"
echo ""

# Configuration
EC2_IP="43.208.201.191"
SSH_KEY="~/dev/th-lab01.pem"

# Calculate date 15 days ago
FIFTEEN_DAYS_AGO=$(date -u -v-15d +"%Y-%m-%d" 2>/dev/null || date -u -d "15 days ago" +"%Y-%m-%d")
echo "Checking messages from: $FIFTEEN_DAYS_AGO to now"
echo ""

# Query for the last 9 water level messages from the past 15 days
echo "1. Querying water_level_readings table..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
SELECT 
    time,
    sensor_id,
    mac_address,
    level_cm,
    voltage,
    rssi,
    location,
    created_at
FROM water_level_readings
WHERE time >= NOW() - INTERVAL '15 days'
ORDER BY time DESC
LIMIT 9;
"
EOF

echo ""
echo "2. Getting total count of messages in the past 15 days..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -t -c "
SELECT COUNT(*) as total_messages_15_days
FROM water_level_readings
WHERE time >= NOW() - INTERVAL '15 days';
"
EOF

echo ""
echo "3. Checking distinct sensor IDs that sent data in the past 15 days..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
SELECT 
    sensor_id,
    COUNT(*) as message_count,
    MIN(time) as first_message,
    MAX(time) as last_message
FROM water_level_readings
WHERE time >= NOW() - INTERVAL '15 days'
GROUP BY sensor_id
ORDER BY last_message DESC;
"
EOF

echo ""
echo "4. Verifying data integrity of the last 9 messages..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
SELECT 
    CASE 
        WHEN sensor_id IS NULL THEN 'Missing sensor_id'
        WHEN mac_address IS NULL THEN 'Missing mac_address'
        WHEN level_cm IS NULL THEN 'Missing level_cm'
        WHEN time IS NULL THEN 'Missing timestamp'
        ELSE 'Complete'
    END as data_status,
    COUNT(*) as count
FROM (
    SELECT * FROM water_level_readings
    WHERE time >= NOW() - INTERVAL '15 days'
    ORDER BY time DESC
    LIMIT 9
) recent_messages
GROUP BY data_status;
"
EOF

echo ""
echo "5. Checking consumer logs for recent activity..."
ssh -i $SSH_KEY ubuntu@$EC2_IP "tail -20 ~/.pm2/logs/sqs-consumer-out.log | grep -E 'water-level|processed|error|failed' || echo 'No recent water-level entries in consumer logs'"

echo ""
echo "=== Summary ==="
echo "The queries above show:"
echo "- The last 9 messages with all their details"
echo "- Total message count in the past 15 days"
echo "- Active sensors and their message frequencies"
echo "- Data integrity status of the recent messages"
echo "- Recent consumer activity logs"