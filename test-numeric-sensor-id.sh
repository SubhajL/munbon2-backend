#!/bin/bash

echo "Testing water level data with numeric sensor ID..."

# Use the actual numeric sensor ID from the data
NUMERIC_ID="2216617412385143"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")

# Create test message with numeric sensor ID
cat > /tmp/numeric-sensor-test.json <<EOF
{
  "sensorType": "water-level",
  "sensorId": "$NUMERIC_ID",
  "timestamp": "$TIMESTAMP",
  "data": {
    "level": 175,
    "voltage": 385,
    "RSSI": -68
  },
  "location": {
    "lat": 14.3754,
    "lng": 102.8756
  },
  "metadata": {
    "source": "numeric-id-test"
  }
}
EOF

echo "Sending message with numeric sensor ID: $NUMERIC_ID"
echo "Expected AWD format: AWD-D977"
echo ""

# Send to SQS
aws sqs send-message \
  --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
  --message-body file:///tmp/numeric-sensor-test.json \
  --region ap-southeast-1

echo "Message sent. Waiting 10 seconds for processing..."
sleep 10

# Check database for converted sensor ID
echo ""
echo "Checking database for AWD-D977 (converted from $NUMERIC_ID)..."
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \"SELECT time, sensor_id, level_cm, voltage FROM water_level_readings WHERE sensor_id = 'AWD-D977' ORDER BY time DESC LIMIT 3;\""

# Check consumer logs
echo ""
echo "Consumer logs (last 20 lines):"
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "tail -20 ~/.pm2/logs/sqs-consumer-out.log | grep -E '(water-level|AWD|sensor_id|2216617412385143)'"

# Cleanup
rm -f /tmp/numeric-sensor-test.json