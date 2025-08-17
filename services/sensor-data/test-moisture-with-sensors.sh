#!/bin/bash

# Test moisture data WITH sensor data (Case 1)
echo "Testing moisture data WITH sensor readings..."

curl -X POST http://${EC2_HOST:-43.208.201.191}:8080/api/sensor-data/moisture/munbon-m2m-moisture \
  -H "Content-Type: application/json" \
  -d '{
  "gw_id": "0001",
  "msg_type": "Interval",
  "date": "2025/07/31",
  "time": "17:06:24",
  "latitude": "14.49726",
  "longitude": "102.15058",
  "temperature": "27.50",
  "humidity": "56.20",
  "head_index": "28.40",
  "batt": "12.92",
  "sensor": [
    {
      "sensor_id": "000D",
      "sensor_utc": "17:03:33",
      "sensor_date": "2025/07/31",
      "sensor_msg_type": "Interval",
      "flood": "no",
      "amb_humid": "50.9",
      "amb_temp": "28.9",
      "humid_hi": "45.5",
      "temp_hi": "26.50",
      "humid_low": "52.3",
      "temp_low": "26.50",
      "sensor_batt": "411"
    }
  ]
}'

echo -e "\n\nResponse received. Check consumer logs for processing."