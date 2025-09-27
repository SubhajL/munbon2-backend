#!/bin/bash

echo "=== Water Level System End-to-End Test ==="
echo "Testing the complete water level data pipeline..."
echo ""

# Configuration
EC2_IP="43.208.201.191"
SENSOR_ID="AWD-TEST-$(date +%s)"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")

# Step 1: Check if consumer is running
echo "1. Checking SQS consumer status..."
ssh -i ~/dev/th-lab01.pem ubuntu@$EC2_IP "pm2 list | grep sqs-consumer"
echo ""

# Step 2: Check current record count
echo "2. Getting current water level record count..."
BEFORE_COUNT=$(ssh -i ~/dev/th-lab01.pem ubuntu@$EC2_IP "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -t -c 'SELECT COUNT(*) FROM water_level_readings;'" | tr -d ' ')
echo "Current records: $BEFORE_COUNT"
echo ""

# Step 3: Send test data to SQS directly (bypass Lambda for testing)
echo "3. Sending test water level data..."
cat > /tmp/test-water-level.json <<EOF
{
  "sensorType": "water-level",
  "sensorId": "$SENSOR_ID",
  "timestamp": "$TIMESTAMP",
  "data": {
    "level": 250,
    "voltage": 385,
    "RSSI": -72,
    "macAddress": "00:11:22:33:44:55"
  },
  "location": {
    "lat": 14.3754,
    "lng": 102.8756
  },
  "metadata": {
    "source": "test-script"
  }
}
EOF

# Send directly to SQS
aws sqs send-message \
  --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
  --message-body file:///tmp/test-water-level.json \
  --region ap-southeast-1

echo "Test message sent to SQS"
echo ""

# Step 4: Wait for processing
echo "4. Waiting 10 seconds for processing..."
sleep 10

# Step 5: Check if data was written
echo "5. Checking for new record..."
AFTER_COUNT=$(ssh -i ~/dev/th-lab01.pem ubuntu@$EC2_IP "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -t -c 'SELECT COUNT(*) FROM water_level_readings;'" | tr -d ' ')
echo "Records after test: $AFTER_COUNT"

# Check if test record exists
echo ""
echo "6. Looking for test record..."
ssh -i ~/dev/th-lab01.pem ubuntu@$EC2_IP "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \"SELECT time, sensor_id, level_cm FROM water_level_readings WHERE sensor_id = '$SENSOR_ID';\""

# Summary
echo ""
echo "=== Test Summary ==="
if [ "$AFTER_COUNT" -gt "$BEFORE_COUNT" ]; then
  echo "✅ SUCCESS: Water level data was successfully processed and written to database"
  echo "Records increased from $BEFORE_COUNT to $AFTER_COUNT"
else
  echo "❌ FAILED: No new records were written"
  echo "Check the consumer logs with: ssh -i ~/dev/th-lab01.pem ubuntu@$EC2_IP 'tail -50 ~/.pm2/logs/sqs-consumer-out.log'"
fi

# Cleanup
rm -f /tmp/test-water-level.json