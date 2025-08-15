#!/bin/bash

echo "=== TESTING GATEWAY 003 (not 0003) WITH SENSOR 0D (not 000D) ==="
echo ""

# Test data with gw_id="003" and sensor_id="0D"
TEST_DATA='{
  "gw_id": "003",
  "latitude": "14.49726",
  "longitude": "102.15058",
  "msg_type": "report",
  "sensor": [
    {
      "sensor_id": "0D",
      "sensor_date": "2025/08/01",
      "sensor_utc": "14:45:00",
      "humid_hi": "55.5",
      "humid_low": "62.3",
      "temp_hi": "29.5",
      "temp_low": "27.3",
      "amb_humid": "78.2",
      "amb_temp": "33.1",
      "flood": "no",
      "sensor_batt": "390"
    }
  ]
}'

# Send test data
echo "Sending test data for gateway 003 (not 0003)..."
curl -X POST \
  -H "Content-Type: application/json" \
  -d "$TEST_DATA" \
  http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture

echo ""
echo ""
echo "Test complete. The sensor ID will be: 003-0D"