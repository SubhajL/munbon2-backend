#!/bin/bash

echo "Sending test water level data to SQS..."

# Create test message - Note the sensorId is at root level, not inside data
cat > /tmp/water-level-test.json <<EOF
{
  "sensorType": "water-level",
  "sensorId": "AWD-TEST-MANUAL",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")",
  "data": {
    "level": 125,
    "voltage": 385,
    "RSSI": -72
  },
  "location": {
    "lat": 14.3754,
    "lng": 102.8756
  },
  "metadata": {
    "source": "manual-test"
  }
}
EOF

# Send to SQS
aws sqs send-message \
  --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
  --message-body file:///tmp/water-level-test.json \
  --region ap-southeast-1

echo "Message sent. Waiting 10 seconds..."
sleep 10

# Check database
echo "Checking database for test record..."
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \"SELECT time, sensor_id, level_cm, voltage FROM water_level_readings WHERE sensor_id = 'AWD-TEST-MANUAL' ORDER BY time DESC LIMIT 1;\""

# Check consumer stats
echo ""
echo "Consumer stats:"
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "curl -s http://localhost:3004/stats"

# Cleanup
rm -f /tmp/water-level-test.json