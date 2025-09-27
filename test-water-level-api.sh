#!/bin/bash

echo "Testing water level API endpoint..."

# Create test payload
PAYLOAD=$(cat <<EOF
{
  "sensorType": "water-level",
  "sensorId": "AWD-API-TEST",
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")",
  "data": {
    "level": 150,
    "voltage": 390,
    "RSSI": -65,
    "macAddress": "00:11:22:33:44:55"
  },
  "location": {
    "lat": 14.3754,
    "lng": 102.8756
  },
  "metadata": {
    "source": "api-test"
  }
}
EOF
)

# Send to API endpoint
echo "Sending data to: https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry"
echo ""
curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  -w "\n\nHTTP Status: %{http_code}\n"

echo ""
echo "Waiting 10 seconds for processing..."
sleep 10

# Check if data was processed
echo ""
echo "Checking database for test record..."
ssh -i ~/dev/th-lab01.pem ubuntu@43.208.201.191 "docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \"SELECT time, sensor_id, level_cm, voltage FROM water_level_readings WHERE sensor_id = 'AWD-API-TEST' ORDER BY time DESC LIMIT 1;\""

# Check SQS queue
echo ""
echo "Checking SQS queue status..."
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
  --attribute-names ApproximateNumberOfMessages \
  --region ap-southeast-1