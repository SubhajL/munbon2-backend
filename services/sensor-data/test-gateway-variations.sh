#!/bin/bash

echo "=== TESTING VARIOUS GATEWAY/SENSOR ID FORMATS ==="
echo ""

# Test 1: gw_id="3" sensor_id="13"
TEST_DATA_1='{
  "gw_id": "3",
  "sensor": [{
    "sensor_id": "13",
    "sensor_date": "2025/08/01",
    "sensor_utc": "14:50:00",
    "humid_hi": "40.5",
    "humid_low": "45.3",
    "sensor_batt": "400"
  }]
}'

# Test 2: gw_id="03" sensor_id="D"
TEST_DATA_2='{
  "gw_id": "03",
  "sensor": [{
    "sensor_id": "D",
    "sensor_date": "2025/08/01",
    "sensor_utc": "14:51:00",
    "humid_hi": "41.5",
    "humid_low": "46.3",
    "sensor_batt": "400"
  }]
}'

echo "Test 1: Sending gw_id='3', sensor_id='13'"
curl -s -X POST -H "Content-Type: application/json" -d "$TEST_DATA_1" \
  http://${EC2_HOST:-43.208.201.191}:8080/api/sensor-data/moisture/munbon-m2m-moisture

echo -e "\n\nTest 2: Sending gw_id='03', sensor_id='D'"
curl -s -X POST -H "Content-Type: application/json" -d "$TEST_DATA_2" \
  http://${EC2_HOST:-43.208.201.191}:8080/api/sensor-data/moisture/munbon-m2m-moisture

echo -e "\n\nExpected sensor IDs: 3-13, 03-D"