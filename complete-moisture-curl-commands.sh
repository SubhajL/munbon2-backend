#!/bin/bash

# Complete CURL commands for all 6 moisture sensors

# Sensor 1 - High Moisture (85%/78%)
curl -X POST "http://43.208.201.191:8080/api/sensor-data/moisture/munbon-m2m-moisture" \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "0003",
    "gateway_msg_type": "Interval",
    "gateway_date": "2025/09/05",
    "gateway_utc": "17:33:40",
    "gps_lat": "13.94555",
    "gps_lng": "100.73404",
    "gw_temp": "32.5",
    "gw_himid": "65.2",
    "sensor": [{
      "sensor_id": "0015",
      "sensor_msg_type": "Interval",
      "sensor_date": "2025/09/05",
      "sensor_utc": "17:33:40",
      "humid_hi": "85",
      "humid_low": "78",
      "temp_hi": "28.5",
      "temp_low": "27.0",
      "amb_humid": "68.5",
      "amb_temp": "31.2",
      "flood": "no",
      "sensor_batt": "412"
    }]
  }'

# Sensor 2 - Medium Moisture (65%/58%)
curl -X POST "http://43.208.201.191:8080/api/sensor-data/moisture/munbon-m2m-moisture" \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "0003",
    "gateway_msg_type": "Interval",
    "gateway_date": "2025/09/05",
    "gateway_utc": "17:33:41",
    "gps_lat": "13.94560",
    "gps_lng": "100.73410",
    "gw_temp": "33.1",
    "gw_himid": "64.8",
    "sensor": [{
      "sensor_id": "0016",
      "sensor_msg_type": "Interval",
      "sensor_date": "2025/09/05",
      "sensor_utc": "17:33:41",
      "humid_hi": "65",
      "humid_low": "58",
      "temp_hi": "29.0",
      "temp_low": "28.0",
      "amb_humid": "66.2",
      "amb_temp": "32.1",
      "flood": "no",
      "sensor_batt": "408"
    }]
  }'

# Sensor 3 - Low Moisture (35%/28%) - Needs irrigation
curl -X POST "http://43.208.201.191:8080/api/sensor-data/moisture/munbon-m2m-moisture" \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "0004",
    "gateway_msg_type": "Interval",
    "gateway_date": "2025/09/05",
    "gateway_utc": "17:33:42",
    "gps_lat": "13.94520",
    "gps_lng": "100.73380",
    "gw_temp": "34.2",
    "gw_himid": "62.1",
    "sensor": [{
      "sensor_id": "0001",
      "sensor_msg_type": "Interval",
      "sensor_date": "2025/09/05",
      "sensor_utc": "17:33:42",
      "humid_hi": "35",
      "humid_low": "28",
      "temp_hi": "30.5",
      "temp_low": "29.5",
      "amb_humid": "60.1",
      "amb_temp": "33.8",
      "flood": "no",
      "sensor_batt": "395"
    }]
  }'

# Sensor 4 - Very High Moisture (95%/92%) - Flood Alert
curl -X POST "http://43.208.201.191:8080/api/sensor-data/moisture/munbon-m2m-moisture" \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "0004",
    "gateway_msg_type": "Interval",
    "gateway_date": "2025/09/05",
    "gateway_utc": "17:33:43",
    "gps_lat": "13.94525",
    "gps_lng": "100.73385",
    "gw_temp": "31.8",
    "gw_himid": "71.3",
    "sensor": [{
      "sensor_id": "0002",
      "sensor_msg_type": "Interval",
      "sensor_date": "2025/09/05",
      "sensor_utc": "17:33:43",
      "humid_hi": "95",
      "humid_low": "92",
      "temp_hi": "27.0",
      "temp_low": "26.5",
      "amb_humid": "72.8",
      "amb_temp": "30.1",
      "flood": "yes",
      "sensor_batt": "401"
    }]
  }'

# Sensor 5 - Normal Moisture (55%/48%)
curl -X POST "http://43.208.201.191:8080/api/sensor-data/moisture/munbon-m2m-moisture" \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "0005",
    "gateway_msg_type": "Interval",
    "gateway_date": "2025/09/05",
    "gateway_utc": "17:33:44",
    "gps_lat": "13.94490",
    "gps_lng": "100.73350",
    "gw_temp": "32.9",
    "gw_himid": "64.5",
    "sensor": [{
      "sensor_id": "0001",
      "sensor_msg_type": "Interval",
      "sensor_date": "2025/09/05",
      "sensor_utc": "17:33:44",
      "humid_hi": "55",
      "humid_low": "48",
      "temp_hi": "29.5",
      "temp_low": "28.5",
      "amb_humid": "65.0",
      "amb_temp": "32.0",
      "flood": "no",
      "sensor_batt": "410"
    }]
  }'

# Sensor 6 - Very Dry (22%/18%) - Urgent irrigation needed
curl -X POST "http://43.208.201.191:8080/api/sensor-data/moisture/munbon-m2m-moisture" \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "0005",
    "gateway_msg_type": "Interval",
    "gateway_date": "2025/09/05",
    "gateway_utc": "17:33:45",
    "gps_lat": "13.94495",
    "gps_lng": "100.73355",
    "gw_temp": "35.1",
    "gw_himid": "58.2",
    "sensor": [{
      "sensor_id": "0002",
      "sensor_msg_type": "Interval",
      "sensor_date": "2025/09/05",
      "sensor_utc": "17:33:45",
      "humid_hi": "22",
      "humid_low": "18",
      "temp_hi": "31.5",
      "temp_low": "30.5",
      "amb_humid": "55.8",
      "amb_temp": "34.5",
      "flood": "no",
      "sensor_batt": "388"
    }]
  }'