#!/bin/bash

# Endpoint configuration
ENDPOINT="http://43.208.201.191:8080/api/sensor-data/moisture/munbon-m2m-moisture"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
DATE=$(date +"%Y/%m/%d")
TIME=$(date +"%H:%M:%S")

echo "=== Sending 6 Moisture Sensor Data to Munbon Endpoint ==="
echo "Endpoint: $ENDPOINT"
echo "Timestamp: $TIMESTAMP"
echo ""

# Sensor 1: High moisture field (recently irrigated)
echo "1. Sending Sensor 1 - High moisture field..."
curl -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "0003",
    "gateway_msg_type": "Interval",
    "gateway_date": "'$DATE'",
    "gateway_utc": "'$TIME'",
    "gps_lat": "13.94555",
    "gps_lng": "100.73404",
    "gw_temp": "32.5",
    "gw_himid": "65.2",
    "sensor": [{
      "sensor_id": "0015",
      "sensor_msg_type": "Interval",
      "sensor_date": "'$DATE'",
      "sensor_utc": "'$TIME'",
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
echo -e "\n"

sleep 1

# Sensor 2: Medium moisture field
echo "2. Sending Sensor 2 - Medium moisture field..."
curl -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "0003",
    "gateway_msg_type": "Interval",
    "gateway_date": "'$DATE'",
    "gateway_utc": "'$TIME'",
    "gps_lat": "13.94560",
    "gps_lng": "100.73410",
    "gw_temp": "33.1",
    "gw_himid": "64.8",
    "sensor": [{
      "sensor_id": "0016",
      "sensor_msg_type": "Interval",
      "sensor_date": "'$DATE'",
      "sensor_utc": "'$TIME'",
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
echo -e "\n"

sleep 1

# Sensor 3: Low moisture field (needs irrigation)
echo "3. Sending Sensor 3 - Low moisture field..."
curl -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "0004",
    "gateway_msg_type": "Interval",
    "gateway_date": "'$DATE'",
    "gateway_utc": "'$TIME'",
    "gps_lat": "13.94520",
    "gps_lng": "100.73380",
    "gw_temp": "34.2",
    "gw_himid": "62.1",
    "sensor": [{
      "sensor_id": "0001",
      "sensor_msg_type": "Interval",
      "sensor_date": "'$DATE'",
      "sensor_utc": "'$TIME'",
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
echo -e "\n"

sleep 1

# Sensor 4: Very high moisture (possible flooding)
echo "4. Sending Sensor 4 - Very high moisture (flood risk)..."
curl -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "0004",
    "gateway_msg_type": "Interval",
    "gateway_date": "'$DATE'",
    "gateway_utc": "'$TIME'",
    "gps_lat": "13.94525",
    "gps_lng": "100.73385",
    "gw_temp": "31.8",
    "gw_himid": "71.3",
    "sensor": [{
      "sensor_id": "0002",
      "sensor_msg_type": "Interval",
      "sensor_date": "'$DATE'",
      "sensor_utc": "'$TIME'",
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
echo -e "\n"

sleep 1

# Sensor 5: Normal moisture level
echo "5. Sending Sensor 5 - Normal moisture level..."
curl -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "0005",
    "gateway_msg_type": "Interval",
    "gateway_date": "'$DATE'",
    "gateway_utc": "'$TIME'",
    "gps_lat": "13.94490",
    "gps_lng": "100.73350",
    "gw_temp": "32.9",
    "gw_himid": "64.5",
    "sensor": [{
      "sensor_id": "0001",
      "sensor_msg_type": "Interval",
      "sensor_date": "'$DATE'",
      "sensor_utc": "'$TIME'",
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
echo -e "\n"

sleep 1

# Sensor 6: Very dry field (urgent irrigation needed)
echo "6. Sending Sensor 6 - Very dry field..."
curl -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "0005",
    "gateway_msg_type": "Interval",
    "gateway_date": "'$DATE'",
    "gateway_utc": "'$TIME'",
    "gps_lat": "13.94495",
    "gps_lng": "100.73355",
    "gw_temp": "35.1",
    "gw_himid": "58.2",
    "sensor": [{
      "sensor_id": "0002",
      "sensor_msg_type": "Interval",
      "sensor_date": "'$DATE'",
      "sensor_utc": "'$TIME'",
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
echo -e "\n"

echo "=== Summary of Sensors Sent ==="
echo "1. Gateway 0003, Sensor 0015: High moisture (85%/78%)"
echo "2. Gateway 0003, Sensor 0016: Medium moisture (65%/58%)"
echo "3. Gateway 0004, Sensor 0001: Low moisture (35%/28%)"
echo "4. Gateway 0004, Sensor 0002: Very high/flood (95%/92%)"
echo "5. Gateway 0005, Sensor 0001: Normal moisture (55%/48%)"
echo "6. Gateway 0005, Sensor 0002: Very dry (22%/18%)"
echo ""
echo "All data sent with realistic field conditions!"