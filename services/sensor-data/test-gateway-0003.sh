#!/bin/bash

echo "=== TESTING GATEWAY 0003 DATA SUBMISSION ==="
echo ""

# Test data mimicking gateway 0003 with sensor 13
TEST_DATA='{
  "gw_id": "0003",
  "latitude": "14.49726",
  "longitude": "102.15058",
  "msg_type": "report",
  "sensor": [
    {
      "sensor_id": "13",
      "sensor_date": "2025/08/01",
      "sensor_utc": "14:30:00",
      "humid_hi": "45.5",
      "humid_low": "52.3",
      "temp_hi": "28.5",
      "temp_low": "26.3",
      "amb_humid": "75.2",
      "amb_temp": "32.1",
      "flood": "no",
      "sensor_batt": "380"
    }
  ]
}'

# Send test data
echo "Sending test data for gateway 0003..."
curl -X POST \
  -H "Content-Type: application/json" \
  -d "$TEST_DATA" \
  http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture

echo ""
echo ""
echo "Test complete. Check logs and database for gateway 0003 data."