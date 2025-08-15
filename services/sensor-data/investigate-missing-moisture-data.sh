#!/bin/bash

# Comprehensive investigation of missing moisture data

SSH_KEY="$HOME/dev/th-lab01.pem"
EC2_HOST="43.209.22.250"

echo "=== COMPREHENSIVE MOISTURE DATA INVESTIGATION ==="
echo "Date: $(date)"
echo "================================================"
echo ""

# 1. Check HTTP server logs for ALL incoming requests in last 24 hours
echo "1. HTTP SERVER - ALL INCOMING MOISTURE REQUESTS (Last 24 hours):"
echo "================================================================"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "echo 'Total requests:' && grep -c 'Received moisture data' /home/ubuntu/.pm2/logs/moisture-http-out.log"
echo ""
echo "Requests by hour (showing last 24 hours):"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep 'Received moisture data' /home/ubuntu/.pm2/logs/moisture-http-out.log | awk '{print substr(\$1,2,13)}' | cut -d: -f1 | sort | uniq -c | tail -24"
echo ""

# 2. Check for any rejected or error responses
echo "2. HTTP SERVER - ERRORS OR REJECTIONS:"
echo "======================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -E 'error|Error|failed|Failed|reject|Invalid' /home/ubuntu/.pm2/logs/moisture-http-*.log | tail -20"
echo ""

# 3. Check what gateways are sending data
echo "3. GATEWAYS DETECTED IN HTTP LOGS:"
echo "==================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep 'gw_id' /home/ubuntu/.pm2/logs/moisture-http-out.log | grep -o 'gw_id[^,]*' | sort | uniq -c | sort -nr | head -20"
echo ""

# 4. Check SQS queue for stuck messages
echo "4. SQS QUEUE STATUS:"
echo "===================="
aws sqs get-queue-attributes \
    --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
    --attribute-names All \
    2>/dev/null | jq -r '.Attributes | {
        ApproximateNumberOfMessages,
        ApproximateNumberOfMessagesNotVisible,
        ApproximateNumberOfMessagesDelayed
    }'
echo ""

# 5. Check consumer processing logs
echo "5. CONSUMER PROCESSING STATUS:"
echo "=============================="
echo "Successfully processed messages (last hour):"
tail -10000 ~/dev/munbon2-backend/services/sensor-data/logs/sensor-consumer-out-*.log | grep -c "Successfully saved moisture sensor reading"
echo ""
echo "Failed processing (last hour):"
tail -10000 ~/dev/munbon2-backend/services/sensor-data/logs/sensor-consumer-*.log | grep -iE "error|failed" | grep -v "No messages" | tail -10
echo ""

# 6. Check database for all gateway data
echo "6. DATABASE - DATA BY GATEWAY (Last 24 hours):"
echo "=============================================="
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
SELECT 
    SUBSTRING(sensor_id, 1, 4) as gateway_id,
    COUNT(*) as record_count,
    MIN(time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok') as earliest_bangkok,
    MAX(time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok') as latest_bangkok
FROM moisture_readings 
WHERE time > NOW() - INTERVAL '24 hours'
GROUP BY SUBSTRING(sensor_id, 1, 4)
ORDER BY gateway_id;"
echo ""

# 7. Check for gaps in data
echo "7. DATABASE - DATA GAPS ANALYSIS:"
echo "================================="
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
WITH time_diffs AS (
    SELECT 
        sensor_id,
        time,
        LAG(time) OVER (PARTITION BY sensor_id ORDER BY time) as prev_time,
        time - LAG(time) OVER (PARTITION BY sensor_id ORDER BY time) as time_gap
    FROM moisture_readings
    WHERE sensor_id LIKE '0003-%'
    AND time > NOW() - INTERVAL '24 hours'
)
SELECT 
    sensor_id,
    COUNT(*) as total_readings,
    AVG(EXTRACT(EPOCH FROM time_gap)/60)::numeric(10,2) as avg_gap_minutes,
    MAX(EXTRACT(EPOCH FROM time_gap)/60)::numeric(10,2) as max_gap_minutes,
    MIN(time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok') as first_reading,
    MAX(time AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok') as last_reading
FROM time_diffs
WHERE time_gap IS NOT NULL
GROUP BY sensor_id
ORDER BY sensor_id;"
echo ""

# 8. Check sensor registry
echo "8. SENSOR REGISTRY STATUS:"
echo "=========================="
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
SELECT sensor_id, sensor_type, last_seen AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Bangkok' as last_seen_bangkok
FROM sensor_registry 
WHERE sensor_id LIKE '0003-%'
ORDER BY sensor_id;"
echo ""

# 9. Look for specific patterns in HTTP logs
echo "9. HTTP LOGS - DETAILED ANALYSIS FOR GATEWAY 0003:"
echo "=================================================="
echo "Last 10 requests from gateway 0003:"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -A20 -B5 '\"gw_id\":\"0*3\"' /home/ubuntu/.pm2/logs/moisture-http-out.log | tail -100"
echo ""

# 10. Check if messages are being sent to SQS
echo "10. MESSAGES SENT TO SQS (from HTTP logs):"
echo "=========================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -c 'Sent to SQS' /home/ubuntu/.pm2/logs/moisture-http-out.log"
echo "vs"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -c 'Received moisture data' /home/ubuntu/.pm2/logs/moisture-http-out.log"
echo "(Should be similar numbers if all valid data is forwarded)"

echo ""
echo "=== END OF INVESTIGATION ==="