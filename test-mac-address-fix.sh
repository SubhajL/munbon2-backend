#!/bin/bash

echo "Testing MAC address-based AWD ID generation..."
echo ""

# Test with one of the problematic sensors
MAC_ADDRESS="16A6AE7B81E9"
EXPECTED_AWD="AWD-81E9"
NUMERIC_ID="22166174123129233"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")

echo "Testing sensor with:"
echo "  MAC Address: $MAC_ADDRESS"
echo "  Expected AWD ID: $EXPECTED_AWD (last 4 chars of MAC)"
echo "  Numeric ID being sent: $NUMERIC_ID"
echo ""

# Create test payload
PAYLOAD=$(cat <<EOF
{
  "sensorType": "water-level",
  "sensorId": "$NUMERIC_ID",
  "timestamp": "$TIMESTAMP",
  "data": {
    "level": 123,
    "voltage": 385,
    "RSSI": -65,
    "macAddress": "$MAC_ADDRESS"
  },
  "location": {
    "lat": 14.3754,
    "lng": 102.8756
  },
  "metadata": {
    "source": "mac-address-fix-test"
  }
}
EOF
)

# Send to SQS
echo "Sending test message to SQS..."
aws sqs send-message \
  --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
  --message-body "$PAYLOAD" \
  --region ap-southeast-1 \
  --output json | jq -r '.MessageId'

echo ""
echo "Waiting 15 seconds for processing..."
sleep 15

# Check database for the correct AWD ID
echo ""
echo "Checking database for correct AWD ID ($EXPECTED_AWD)..."
RESULT=$(ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -t -c \"SELECT COUNT(*) FROM water_level_readings WHERE sensor_id = '$EXPECTED_AWD' AND time >= NOW() - INTERVAL '1 minute';\"" | tr -d ' ')

if [ "$RESULT" -gt "0" ]; then
  echo "✅ SUCCESS: Found record with correct AWD ID!"
  ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \"SELECT time, sensor_id, level_cm FROM water_level_readings WHERE sensor_id = '$EXPECTED_AWD' AND time >= NOW() - INTERVAL '1 minute' ORDER BY time DESC LIMIT 1;\""
else
  echo "❌ FAILED: No record found with correct AWD ID"
  echo ""
  echo "Checking if it was saved with wrong ID..."
  ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \"SELECT time, sensor_id, level_cm FROM water_level_readings WHERE time >= NOW() - INTERVAL '1 minute' ORDER BY time DESC LIMIT 5;\""
fi

# Check consumer logs
echo ""
echo "Recent consumer logs:"
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "tail -30 ~/.pm2/logs/sqs-consumer-out.log | grep -E 'formattedId|$MAC_ADDRESS|$EXPECTED_AWD' | tail -5"