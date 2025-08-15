#!/bin/bash

echo "=== TESTING MINIMAL SENSOR DATA (only sensor_id) ==="
echo ""

# Test data with only sensor_id, missing all sensor values
TEST_DATA='{
  "gw_id": "0003",
  "latitude": "14.49726",
  "longitude": "102.15058",
  "msg_type": "report",
  "sensor": [
    {
      "sensor_id": "0D",
      "sensor_date": "2025/08/01",
      "sensor_utc": "15:00:00"
    }
  ]
}'

echo "Sending data with only sensor_id (no humid_hi, humid_low, etc.)..."
curl -X POST \
  -H "Content-Type: application/json" \
  -d "$TEST_DATA" \
  http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture

echo ""
echo ""
echo "Expected behavior: Data saved with humid values as 0, low quality score"