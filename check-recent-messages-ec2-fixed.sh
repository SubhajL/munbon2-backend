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

# First check the table structure
echo "0. Checking water_level_readings table structure..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "\d water_level_readings" | head -20
EOF

echo ""
echo "1. Querying last 9 water level messages from the past 15 days..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
SELECT 
    time,
    sensor_id,
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
echo "3. Message distribution by sensor in the past 15 days..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
SELECT 
    sensor_id,
    COUNT(*) as message_count,
    MIN(time) as first_message,
    MAX(time) as last_message,
    ROUND(AVG(level_cm)::numeric, 2) as avg_level_cm
FROM water_level_readings
WHERE time >= NOW() - INTERVAL '15 days'
GROUP BY sensor_id
ORDER BY last_message DESC;
"
EOF

echo ""
echo "4. Data integrity check for the last 9 messages..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
WITH recent_messages AS (
    SELECT * FROM water_level_readings
    WHERE time >= NOW() - INTERVAL '15 days'
    ORDER BY time DESC
    LIMIT 9
)
SELECT 
    sensor_id,
    time,
    CASE 
        WHEN sensor_id IS NULL THEN 'Missing sensor_id'
        WHEN level_cm IS NULL THEN 'Missing level_cm'
        WHEN time IS NULL THEN 'Missing timestamp'
        WHEN voltage IS NULL THEN 'Missing voltage'
        ELSE 'Complete'
    END as data_status,
    level_cm,
    voltage,
    rssi
FROM recent_messages
ORDER BY time DESC;
"
EOF

echo ""
echo "5. Hourly message count for the last 24 hours..."
ssh -i $SSH_KEY ubuntu@$EC2_IP << 'EOF'
docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c "
SELECT 
    date_trunc('hour', time) as hour,
    COUNT(*) as messages_received,
    COUNT(DISTINCT sensor_id) as unique_sensors
FROM water_level_readings
WHERE time >= NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC
LIMIT 24;
"
EOF

echo ""
echo "6. Checking consumer status and recent logs..."
ssh -i $SSH_KEY ubuntu@$EC2_IP "pm2 list | grep -E 'sqs-consumer|online' || echo 'Consumer status check failed'"
echo ""
ssh -i $SSH_KEY ubuntu@$EC2_IP "tail -30 ~/.pm2/logs/sqs-consumer-out.log | grep -E 'water-level|processed|error|failed' | tail -10 || echo 'No recent water-level entries in consumer logs'"

echo ""
echo "=== Write Status Summary ==="
echo "Based on the data above:"
echo "1. Total messages in past 15 days: Check count above"
echo "2. Last 9 messages are shown with timestamps and data integrity"
echo "3. Active sensors and their message frequencies are listed"
echo "4. Hourly distribution shows write patterns"
echo "5. Consumer status indicates if writes are currently active"