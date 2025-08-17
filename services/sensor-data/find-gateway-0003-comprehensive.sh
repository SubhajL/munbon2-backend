#!/bin/bash

SSH_KEY="$HOME/dev/th-lab01.pem"
EC2_HOST="${EC2_HOST:-43.208.201.191}"

echo "=== COMPREHENSIVE SEARCH FOR GATEWAY 0003 / SENSOR 13 ==="
echo "Time: $(date)"
echo ""

# 1. Search all PM2 logs
echo "1. SEARCHING ALL PM2 LOGS ON EC2:"
echo "================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "find /home/ubuntu/.pm2/logs -name '*.log' -exec grep -l '0003\\|03' {} \; 2>/dev/null"
echo ""

# 2. Search for sensor_id containing 13
echo "2. SEARCHING FOR SENSOR_ID 13 IN HTTP LOGS:"
echo "==========================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -E 'sensor_id.*:.*\".*13' /home/ubuntu/.pm2/logs/moisture-http-out.log | head -20"
echo ""

# 3. Check all data payloads
echo "3. ALL UNIQUE GATEWAY IDs RECEIVED:"
echo "==================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -o '\"gw_id\"[[:space:]]*:[[:space:]]*\"[^\"]*\"' /home/ubuntu/.pm2/logs/moisture-http-out.log | sort -u"
echo ""

# 4. Check SQS messages
echo "4. CHECKING SQS QUEUE FOR PENDING MESSAGES:"
echo "==========================================="
aws sqs receive-message \
    --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
    --max-number-of-messages 10 \
    --visibility-timeout 0 \
    2>/dev/null | jq -r '.Messages[]?.Body' | grep -E "0003|sensor.*13" || echo "No matching messages in queue"
echo ""

# 5. Check consumer logs more thoroughly
echo "5. CONSUMER LOGS - ALL FILES:"
echo "============================="
grep -h "0003" ~/dev/munbon2-backend/services/sensor-data/logs/sensor-consumer-*.log 2>/dev/null | tail -10 || echo "No matches found"
echo ""

# 6. Database search with LIKE patterns
echo "6. DATABASE SEARCH WITH PATTERNS:"
echo "================================="
docker exec munbon-timescaledb psql -U postgres -d sensor_data -c "
SELECT DISTINCT sensor_id, COUNT(*) as count
FROM moisture_readings 
WHERE sensor_id LIKE '%03%' OR sensor_id LIKE '%13%'
GROUP BY sensor_id
ORDER BY sensor_id;"

echo ""
# 7. Check if data might be in sensor_readings instead
echo "7. SENSOR_READINGS TABLE - RAW DATA:"
echo "===================================="
docker exec munbon-timescaledb psql -U postgres -d sensor_data -c "
SELECT time AT TIME ZONE 'Asia/Bangkok' as local_time,
       sensor_id,
       value::text
FROM sensor_readings 
WHERE sensor_type = 'moisture' 
  AND (value::text LIKE '%0003%' OR value::text LIKE '%\"13\"%')
ORDER BY time DESC
LIMIT 5;"

echo ""
echo "=== END OF COMPREHENSIVE SEARCH ==="