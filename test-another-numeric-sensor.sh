#!/bin/bash

echo "Testing sensor ID mapping with another numeric sensor..."

# Use the second numeric sensor ID from our data
NUMERIC_ID="222410831183230"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")

# Expected conversion: 222410831183230 (decimal) = CA480E963D7E (hex) = AWD-3D7E
EXPECTED_AWD="AWD-3D7E"

echo "Numeric sensor ID: $NUMERIC_ID"
echo "Expected AWD format: $EXPECTED_AWD"
echo ""

# Create test message
cat > /tmp/test-sensor-2.json <<EOF
{
  "sensorType": "water-level",
  "sensorId": "$NUMERIC_ID",
  "timestamp": "$TIMESTAMP",
  "data": {
    "level": 150,
    "voltage": 395,
    "RSSI": -65
  },
  "location": {
    "lat": 14.5678,
    "lng": 102.9876
  },
  "metadata": {
    "source": "numeric-mapping-test-2"
  }
}
EOF

# Send to SQS
echo "Sending message to SQS..."
aws sqs send-message \
  --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
  --message-body file:///tmp/test-sensor-2.json \
  --region ap-southeast-1

echo "Waiting 10 seconds for processing..."
sleep 10

# Check database
echo ""
echo "Checking database for $EXPECTED_AWD..."
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \"SELECT time, sensor_id, level_cm, voltage FROM water_level_readings WHERE sensor_id = '$EXPECTED_AWD' ORDER BY time DESC LIMIT 3;\""

# Check all recent water level data
echo ""
echo "All water level data from last 5 minutes:"
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \"SELECT time, sensor_id, level_cm, voltage FROM water_level_readings WHERE time >= NOW() - INTERVAL '5 minutes' ORDER BY time DESC;\""

# Cleanup
rm -f /tmp/test-sensor-2.json