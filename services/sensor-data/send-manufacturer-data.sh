#!/bin/bash

echo "=== SENDING MANUFACTURER'S MOISTURE DATA ==="
echo ""

# Manufacturer's data
DATA='{"gw_id":"3","msg_type":"Interval","date":"2025/08/01","time":"15:38:06","latitude":"13.94551","longitude":"100.73405","temperature":"26.60","humidity":"48.30","head_index":"26.97","batt":"12.27","sensor":[{"sensor_id":"13","sensor_utc":"15:36:34","sensor_date":"2025/08/01","sensor_msg_type":"Interval","flood":"no","amb_humid":"39.5","amb_temp":"26.4","humid_hi":"018","temp_hi":"23.00","humid_low":"018","temp_low":"22.50","sensor_batt":"406"},{"sensor_id":"13","sensor_utc":"15:37:41","sensor_date":"2025/08/01","sensor_msg_type":"Interval","flood":"no","amb_humid":"39.7","amb_temp":"26.5","humid_hi":"018","temp_hi":"23.00","humid_low":"018","temp_low":"22.00","sensor_batt":"406"}]}'

echo "Sending data with:"
echo "- Gateway ID: 3"
echo "- Sensor ID: 13 (2 readings)"
echo "- Location: 13.94551, 100.73405"
echo "- Moisture values: 18% (both readings)"
echo ""

# Send the data
curl -X POST \
  -H "Content-Type: application/json" \
  -d "$DATA" \
  http://${EC2_HOST:-43.208.201.191}:8080/api/sensor-data/moisture/munbon-m2m-moisture

echo ""
echo ""
echo "Data sent. Expected sensor IDs in database: 3-13"