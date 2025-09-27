#!/bin/bash

EC2_HOST="43.208.201.191"
ENDPOINT="http://${EC2_HOST}:8080/api/sensor-data/moisture/munbon-m2m-moisture"

echo "=== Monitoring Moisture Data Ingestion ==="
echo "Endpoint: $ENDPOINT"
echo ""

# Generate unique test data
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TEST_ID="monitor-$(date +%s)"

# Test data matching the actual sensor format
TEST_DATA='{
  "gw_id": "'$TEST_ID'",
  "gateway_msg_type": "Test",
  "gateway_date": "'$(date +"%Y/%m/%d")'",
  "gateway_utc": "'$(date +"%H:%M:%S")'",
  "gps_lat": "13.7563",
  "gps_lng": "100.5018",
  "gw_temp": "32.5",
  "gw_himid": "65.2",
  "sensor": [{
    "sensor_id": "1",
    "sensor_msg_type": "Test",
    "sensor_date": "'$(date +"%Y/%m/%d")'",
    "sensor_utc": "'$(date +"%H:%M:%S")'",
    "humid_hi": "'$(shuf -i 40-80 -n 1)'",
    "humid_low": "'$(shuf -i 30-70 -n 1)'",
    "temp_hi": "'$(shuf -i 25-35 -n 1)'.5",
    "temp_low": "'$(shuf -i 23-33 -n 1)'.0",
    "amb_humid": "'$(shuf -i 50-80 -n 1)'.5",
    "amb_temp": "'$(shuf -i 28-38 -n 1)'.2",
    "flood": "no",
    "sensor_batt": "405"
  }]
}'

echo "Sending test moisture data with ID: $TEST_ID"
echo "Data format: Full sensor payload with nested structure"
echo ""

# Send the data
response=$(curl -s -w "\n%{http_code}" -X POST $ENDPOINT \
  -H "Content-Type: application/json" \
  -d "$TEST_DATA" 2>&1)

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | head -n-1)

echo "Response HTTP Code: $http_code"
echo "Response Body: $body"
echo ""

if [ "$http_code" == "200" ]; then
    echo "✅ Success! Data was accepted by the ingestion endpoint"
    echo ""
    echo "Summary:"
    echo "- Test Gateway ID: $TEST_ID"
    echo "- Timestamp: $TIMESTAMP"
    echo "- The data should now be in the PostgreSQL database"
    echo ""
    echo "To verify the data was saved, you need:"
    echo "1. SSH access with the key: ~/dev/th-lab01.pem"
    echo "2. Or deploy the unified-api.js to query the data"
else
    echo "❌ Failed! HTTP Code: $http_code"
fi