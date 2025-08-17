#!/bin/bash

SSH_KEY="$HOME/dev/th-lab01.pem"
EC2_HOST="${EC2_HOST:-43.208.201.191}"

echo "=== COMPREHENSIVE MOISTURE DATA PIPELINE DEBUG ==="
echo "Time: $(date)"
echo ""

# 1. Check if ANY valid moisture data has been received recently
echo "1. CHECKING HTTP ENDPOINT FOR VALID MOISTURE DATA (Last 2 hours):"
echo "================================================================"
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -B2 -A10 'Received valid moisture' /home/ubuntu/.pm2/logs/moisture-http-out.log | grep -v 'empty' | tail -50"
echo ""

# 2. Check if valid data was sent to SQS
echo "2. CHECKING IF VALID DATA WAS SENT TO SQS:"
echo "=========================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep 'Sent to SQS successfully' /home/ubuntu/.pm2/logs/moisture-http-out.log | grep -v 'undefined' | tail -20"
echo ""

# 3. Check SQS queue status
echo "3. SQS QUEUE STATUS:"
echo "===================="
aws sqs get-queue-attributes \
    --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
    --attribute-names All \
    2>/dev/null | jq '{
        Messages: .Attributes.ApproximateNumberOfMessages,
        InFlight: .Attributes.ApproximateNumberOfMessagesNotVisible,
        Created: .Attributes.CreatedTimestamp,
        LastModified: .Attributes.LastModifiedTimestamp
    }'
echo ""

# 4. Check if consumer is running
echo "4. CONSUMER STATUS:"
echo "==================="
pm2 list | grep sensor-consumer
echo ""

# 5. Check consumer logs for moisture processing
echo "5. CONSUMER MOISTURE PROCESSING (Last 100 lines):"
echo "================================================="
tail -1000 ~/dev/munbon2-backend/services/sensor-data/logs/sensor-consumer-out-*.log | grep -A10 -B2 "Processing.*moisture" | tail -50
echo ""

# 6. Check for ANY moisture data in database
echo "6. DATABASE MOISTURE DATA CHECK:"
echo "================================"
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d sensor_data -c "
SELECT 
    COUNT(*) as total_records,
    MIN(recorded_at) as earliest,
    MAX(recorded_at) as latest
FROM moisture_readings;"

echo ""
echo "Recent moisture readings:"
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d sensor_data -c "
SELECT sensor_id, recorded_at, surface_moisture, deep_moisture 
FROM moisture_readings 
ORDER BY recorded_at DESC 
LIMIT 10;"

echo ""
# 7. Check sensor_readings table for moisture type
echo "7. SENSOR_READINGS TABLE (moisture type):"
echo "========================================="
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -d sensor_data -c "
SELECT 
    sensor_id, 
    recorded_at, 
    data->>'humid_hi' as surface,
    data->>'humid_low' as deep
FROM sensor_readings 
WHERE sensor_type = 'moisture' 
ORDER BY recorded_at DESC 
LIMIT 10;"

echo ""
# 8. Check for consumer errors
echo "8. CONSUMER ERROR LOGS:"
echo "======================="
tail -500 ~/dev/munbon2-backend/services/sensor-data/logs/sensor-consumer-error-*.log | grep -v "^$" | tail -20

echo ""
# 9. Check specific gateway data
echo "9. CHECKING FOR SPECIFIC GATEWAY DATA (0001, 0002):"
echo "===================================================="
ssh -i $SSH_KEY ubuntu@$EC2_HOST "grep -E 'gw_id.*(0001|0002)' /home/ubuntu/.pm2/logs/moisture-http-out.log | tail -20"

echo ""
echo "=== END OF DEBUG REPORT ==="