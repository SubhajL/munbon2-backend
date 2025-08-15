#!/bin/bash

# Test moisture data WITHOUT sensor data (Case 2)
echo "Testing moisture data WITHOUT sensor readings..."

curl -X POST http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture \
  -H "Content-Type: application/json" \
  -d '{
  "gw_id": "0001",
  "msg_type": "Interval",
  "date": "2025/07/31",
  "time": "17:07:29",
  "latitude": "14.49726",
  "longitude": "102.15058",
  "temperature": "26.20",
  "humidity": "40.20",
  "head_index": "25.92",
  "batt": "11.93",
  "sensor": [
    {
      "sensor_id": "",
      "sensor_utc": "00:00:00",
      "sensor_date": "0000/00/00",
      "sensor_msg_type": "",
      "flood": "",
      "amb_humid": "",
      "amb_temp": "",
      "humid_hi": "",
      "temp_hi": "",
      "humid_low": "",
      "temp_low": "",
      "sensor_batt": ""
    }
  ]
}'

echo -e "\n\nResponse received. Check consumer logs for processing."