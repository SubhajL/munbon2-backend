#!/bin/bash

SSH_KEY="$HOME/dev/th-lab01.pem"
EC2_HOST="${EC2_HOST:-43.208.201.191}"

echo "=== ANALYZING SPECIFIC MOISTURE DATA SET ==="
echo "Gateway: 3, Sensor: 13"
echo "Timestamps: 17:02:02 and 17:03:09 UTC"
echo "Date: 2025/08/01"
echo "Moisture values: 16%"
echo ""

# 1. Check HTTP logs for this specific data
echo "1. CHECKING HTTP LOGS FOR THIS DATA:"
echo "====================================="
echo "Searching for sensor data with 17:02:02 or 17:03:09..."
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -E '17:02:02|17:03:09' /home/ubuntu/.pm2/logs/moisture-http-out.log | grep -B10 -A10 'sensor' | tail -50"

echo ""
echo "2. CHECKING FOR MOISTURE VALUE 016:"
echo "===================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep '016' /home/ubuntu/.pm2/logs/moisture-http-out.log | grep -B5 -A5 'humid' | tail -30"

echo ""
echo "3. CHECKING DATABASE FOR THESE TIMESTAMPS:"
echo "=========================================="
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
SELECT 
    sensor_id,
    time AT TIME ZONE 'UTC' as utc_time,
    time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok' as bangkok_time,
    moisture_surface_pct,
    moisture_deep_pct,
    ambient_temp_c
FROM moisture_readings 
WHERE (sensor_id LIKE '%3-13' OR sensor_id LIKE '%03-13' OR sensor_id LIKE '%003-13')
  AND time::date = '2025-08-01'
  AND (
    time::time BETWEEN '17:02:00'::time AND '17:02:05'::time OR
    time::time BETWEEN '17:03:07'::time AND '17:03:12'::time
  )
ORDER BY time;"

echo ""
echo "4. CHECKING FOR 16% MOISTURE IN DATABASE:"
echo "=========================================="
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
SELECT 
    sensor_id,
    time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok' as bangkok_time,
    moisture_surface_pct,
    moisture_deep_pct,
    ambient_temp_c
FROM moisture_readings 
WHERE (sensor_id LIKE '%-13')
  AND moisture_surface_pct = 16
  AND time::date = '2025-08-01'
ORDER BY time DESC;"

echo ""
echo "5. CHECKING CONSUMER LOGS:"
echo "=========================="
tail -2000 ~/dev/munbon2-backend/services/sensor-data/logs/sensor-consumer-out-*.log | grep -E "17:02:02|17:03:09|humid.*016" | tail -20

echo ""
echo "6. CHECKING SQS QUEUE:"
echo "======================"
aws sqs receive-message \
    --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
    --max-number-of-messages 10 \
    --visibility-timeout 0 \
    2>/dev/null | jq -r '.Messages[]?.Body' | grep -E "17:02:02|17:03:09|016" || echo "No matching messages in SQS"

echo ""
echo "=== END OF ANALYSIS ===="