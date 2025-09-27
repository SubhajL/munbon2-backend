#!/bin/bash

echo "=== FINAL E2E TEST WITH CORRECT SENSOR ID MAPPING ==="
echo ""

# Test with numeric ID that has known mapping
NUMERIC_ID="222410831183230"
EXPECTED_AWD="AWD-B7E6"  # From sensor registry
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")

echo "1. Testing with numeric sensor ID: $NUMERIC_ID"
echo "   Expected mapping: $EXPECTED_AWD (from sensor registry)"
echo ""

# Create test payload
PAYLOAD=$(cat <<EOF
{
  "sensorType": "water-level",
  "sensorId": "$NUMERIC_ID",
  "timestamp": "$TIMESTAMP",
  "data": {
    "level": 250,
    "voltage": 400,
    "RSSI": -75,
    "macAddress": "16186C1FB7E6"
  },
  "location": {
    "lat": 13.7563,
    "lng": 100.5018
  },
  "metadata": {
    "source": "final-e2e-test",
    "test": "correct-mapping"
  }
}
EOF
)

# Send directly to SQS (bypass API for cleaner test)
echo "2. Sending to SQS queue..."
aws sqs send-message \
  --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
  --message-body "$PAYLOAD" \
  --region ap-southeast-1 \
  --output json | jq -r '.MessageId'

echo ""
echo "3. Waiting 10 seconds for processing..."
sleep 10

# Check database for the mapped sensor ID
echo ""
echo "4. Checking database for mapped sensor ID ($EXPECTED_AWD)..."
RESULT=$(ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -t -c \"SELECT COUNT(*) FROM water_level_readings WHERE sensor_id = '$EXPECTED_AWD' AND time >= NOW() - INTERVAL '1 minute';\"" | tr -d ' ')

if [ "$RESULT" -gt "0" ]; then
  echo "✅ SUCCESS: Found $RESULT record(s) with correct sensor ID mapping!"
  echo ""
  echo "Latest record:"
  ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \"SELECT time, sensor_id, level_cm, voltage FROM water_level_readings WHERE sensor_id = '$EXPECTED_AWD' ORDER BY time DESC LIMIT 1;\""
else
  echo "❌ FAILED: No records found with expected sensor ID"
  echo ""
  echo "Checking if data was written with numeric ID instead..."
  ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \"SELECT time, sensor_id, level_cm, voltage FROM water_level_readings WHERE sensor_id = '$NUMERIC_ID' AND time >= NOW() - INTERVAL '1 minute' ORDER BY time DESC LIMIT 1;\""
fi

# Check consumer logs
echo ""
echo "5. Consumer log entries:"
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "tail -30 ~/.pm2/logs/sqs-consumer-out.log | grep -E '(222410831183230|AWD-B7E6|No mapping found|Formatted water level)' | tail -5"

# Summary of all recent water level data
echo ""
echo "6. All water level data from last 2 minutes:"
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \"SELECT time, sensor_id, level_cm, voltage FROM water_level_readings WHERE time >= NOW() - INTERVAL '2 minutes' ORDER BY time DESC;\""