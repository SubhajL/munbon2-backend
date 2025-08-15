#!/bin/bash

# Test moisture data with multiple sensors
echo "Testing moisture data with multiple sensor readings..."

curl -X POST http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture \
  -H "Content-Type: application/json" \
  -d '{
  "gw_id": "0002",
  "msg_type": "Interval",
  "date": "2025/07/31",
  "time": "17:30:00",
  "latitude": "14.49726",
  "longitude": "102.15058",
  "temperature": "28.50",
  "humidity": "62.20",
  "head_index": "29.40",
  "batt": "12.85",
  "sensor": [
    {
      "sensor_id": "001A",
      "sensor_utc": "17:25:00",
      "sensor_date": "2025/07/31",
      "sensor_msg_type": "Interval",
      "flood": "no",
      "amb_humid": "55.5",
      "amb_temp": "27.8",
      "humid_hi": "38.2",
      "temp_hi": "26.20",
      "humid_low": "48.7",
      "temp_low": "25.90",
      "sensor_batt": "405"
    },
    {
      "sensor_id": "001B",
      "sensor_utc": "17:25:30",
      "sensor_date": "2025/07/31",
      "sensor_msg_type": "Interval",
      "flood": "yes",
      "amb_humid": "58.2",
      "amb_temp": "27.5",
      "humid_hi": "72.5",
      "temp_hi": "25.80",
      "humid_low": "85.3",
      "temp_low": "25.60",
      "sensor_batt": "398"
    }
  ]
}'

echo -e "\n\nResponse received. Check consumer logs for processing."