#!/bin/bash

echo "=== WATER LEVEL E2E TEST WITH SENSOR ID MAPPING ==="
echo "Testing complete flow: API Gateway → Lambda → SQS → Consumer → Database"
echo ""

# Configuration
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
NUMERIC_ID="2216617412385143"
EXPECTED_AWD="AWD-D977"

echo "1. Testing with numeric sensor ID: $NUMERIC_ID"
echo "   Expected AWD format: $EXPECTED_AWD"
echo ""

# Create test payload
PAYLOAD=$(cat <<EOF
{
  "sensorType": "water-level",
  "sensorId": "$NUMERIC_ID",
  "timestamp": "$TIMESTAMP",
  "data": {
    "level": 200,
    "voltage": 390,
    "RSSI": -70
  },
  "location": {
    "lat": 14.3754,
    "lng": 102.8756
  },
  "metadata": {
    "source": "e2e-test",
    "test": "sensor-id-mapping"
  }
}
EOF
)

# Step 1: Send via API Gateway
echo "2. Sending data via API Gateway..."
API_RESPONSE=$(curl -s -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  -w "\nHTTP_STATUS:%{http_code}")

HTTP_STATUS=$(echo "$API_RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
echo "   API Response Status: $HTTP_STATUS"

# Step 2: Check SQS queue
echo ""
echo "3. Checking SQS queue status..."
sleep 3
SQS_COUNT=$(aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
  --attribute-names ApproximateNumberOfMessages \
  --region ap-southeast-1 \
  --query 'Attributes.ApproximateNumberOfMessages' \
  --output text)
echo "   Messages in queue: $SQS_COUNT"

# Step 3: Check consumer status
echo ""
echo "4. Checking consumer status..."
CONSUMER_STATUS=$(ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "pm2 list | grep sqs-consumer | awk '{print \$12}'")
echo "   Consumer status: $CONSUMER_STATUS"

# Step 4: Wait for processing
echo ""
echo "5. Waiting 10 seconds for processing..."
sleep 10

# Step 5: Check database for both formats
echo ""
echo "6. Checking database for water level data..."
echo "   Looking for numeric ID: $NUMERIC_ID"
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \"SELECT time, sensor_id, level_cm, voltage FROM water_level_readings WHERE sensor_id = '$NUMERIC_ID' AND time >= NOW() - INTERVAL '1 minute' ORDER BY time DESC LIMIT 1;\""

echo ""
echo "   Looking for AWD format: $EXPECTED_AWD"
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \"SELECT time, sensor_id, level_cm, voltage FROM water_level_readings WHERE sensor_id = '$EXPECTED_AWD' AND time >= NOW() - INTERVAL '1 minute' ORDER BY time DESC LIMIT 1;\""

# Step 6: Check consumer logs for processing
echo ""
echo "7. Checking consumer logs for sensor ID mapping..."
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "tail -50 ~/.pm2/logs/sqs-consumer-out.log | grep -E '(Formatted water level|originalId|formattedId|$NUMERIC_ID|$EXPECTED_AWD)' | tail -5"

# Step 7: Summary
echo ""
echo "=== TEST SUMMARY ==="
RECENT_COUNT=$(ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -t -c \"SELECT COUNT(*) FROM water_level_readings WHERE time >= NOW() - INTERVAL '1 minute';\"" | tr -d ' ')

if [ "$RECENT_COUNT" -gt "0" ]; then
  echo "✅ SUCCESS: Found $RECENT_COUNT new water level record(s) in the last minute"
  echo ""
  echo "Recent water level data:"
  ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \"SELECT time, sensor_id, level_cm, voltage FROM water_level_readings WHERE time >= NOW() - INTERVAL '1 minute' ORDER BY time DESC;\""
else
  echo "❌ FAILED: No new water level records found"
  echo ""
  echo "Troubleshooting info:"
  echo "- API Gateway response: $HTTP_STATUS"
  echo "- SQS messages: $SQS_COUNT"
  echo "- Consumer status: $CONSUMER_STATUS"
fi