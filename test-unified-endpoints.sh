#!/bin/bash

# Test all unified sensor endpoints
echo "🧪 Testing Unified Sensor Endpoints"
echo "==================================="

EC2_HOST=${EC2_HOST:-43.208.201.191}
PORT=8080

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "🎯 Target: http://$EC2_HOST:$PORT"
echo ""

# 1. Test Moisture Endpoint
echo -e "${YELLOW}1. Testing Moisture Endpoint${NC}"
echo "------------------------------"

MOISTURE_DATA='{
  "gw_id": "0003",
  "gateway_msg_type": "Interval",
  "gateway_date": "2025/09/10",
  "gateway_utc": "10:30:00",
  "gps_lat": "13.94551",
  "gps_lng": "100.73405",
  "gw_temp": "32.5",
  "gw_himid": "65.2",
  "sensor": [
    {
      "sensor_id": "13",
      "humid_hi": "75",
      "humid_low": "68",
      "temp_hi": "28.5",
      "temp_low": "27.8",
      "amb_humid": "62.3",
      "amb_temp": "31.2",
      "flood": "no",
      "sensor_batt": "385"
    }
  ]
}'

echo "Sending moisture data..."
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST \
  "http://$EC2_HOST:$PORT/api/sensor-data/moisture/munbon-moisture-field" \
  -H "Content-Type: application/json" \
  -d "$MOISTURE_DATA")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1 | cut -d':' -f2)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
  echo -e "${GREEN}✓ Moisture endpoint: OK ($HTTP_CODE)${NC}"
  echo "Response: $BODY"
else
  echo -e "${RED}✗ Moisture endpoint: FAILED ($HTTP_CODE)${NC}"
  echo "Response: $BODY"
fi

echo ""

# 2. Test Water Level Endpoint
echo -e "${YELLOW}2. Testing Water Level Endpoint${NC}"
echo "---------------------------------"

WATER_LEVEL_DATA='{
  "sensorType": "water-level",
  "sensorId": "AWD-TEST-001",
  "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")'",
  "data": {
    "level": 125,
    "voltage": 380,
    "RSSI": -72,
    "macAddress": "AA:BB:CC:DD:EE:FF"
  },
  "location": {
    "lat": 14.3754,
    "lng": 102.8756
  },
  "metadata": {
    "source": "unified-test"
  }
}'

echo "Sending water level data..."
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST \
  "http://$EC2_HOST:$PORT/api/sensor-data/water-level/munbon-level-gate" \
  -H "Content-Type: application/json" \
  -d "$WATER_LEVEL_DATA")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1 | cut -d':' -f2)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
  echo -e "${GREEN}✓ Water level endpoint: OK ($HTTP_CODE)${NC}"
  echo "Response: $BODY"
else
  echo -e "${RED}✗ Water level endpoint: FAILED ($HTTP_CODE)${NC}"
  echo "Response: $BODY"
fi

echo ""

# 3. Test AOS Weather Endpoint
echo -e "${YELLOW}3. Testing AOS Weather Endpoint${NC}"
echo "---------------------------------"

AOS_DATA='{
  "station_id": "AOS-001",
  "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")'",
  "location": {
    "lat": 13.7563,
    "lng": 100.5018
  },
  "data": {
    "rainfall_mm": 2.5,
    "temperature_celsius": 28.5,
    "humidity_percentage": 75,
    "wind_speed_ms": 3.2,
    "wind_direction_degrees": 180,
    "pressure_hpa": 1013.25,
    "solar_radiation_wm2": 650,
    "evapotranspiration_mm": 4.2
  }
}'

echo "Sending AOS weather data..."
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST \
  "http://$EC2_HOST:$PORT/api/sensor-data/aos/munbon-aos-field" \
  -H "Content-Type: application/json" \
  -d "$AOS_DATA")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1 | cut -d':' -f2)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
  echo -e "${GREEN}✓ AOS endpoint: OK ($HTTP_CODE)${NC}"
  echo "Response: $BODY"
else
  echo -e "${RED}✗ AOS endpoint: FAILED ($HTTP_CODE)${NC}"
  echo "Response: $BODY"
fi

echo ""

# 4. Check Statistics
echo -e "${YELLOW}4. Checking Statistics${NC}"
echo "----------------------"

STATS=$(curl -s "http://$EC2_HOST:$PORT/api/stats" | jq .)
echo "$STATS"

echo ""

# 5. Verify data in database
echo -e "${YELLOW}5. Verifying Data in Database${NC}"
echo "------------------------------"

# Check moisture data
echo "Recent moisture readings:"
ssh -i ~/dev/th-lab01.pem ubuntu@$EC2_HOST << 'EOF'
  docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \
    "SELECT time, sensor_id, moisture_surface_pct, moisture_deep_pct 
     FROM moisture_readings 
     WHERE sensor_id LIKE '%0013' 
     ORDER BY time DESC LIMIT 3;"
EOF

echo ""
echo "Recent water level readings:"
ssh -i ~/dev/th-lab01.pem ubuntu@$EC2_HOST << 'EOF'
  docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \
    "SELECT time, sensor_id, level_cm, voltage 
     FROM water_level_readings 
     WHERE sensor_id LIKE 'AWD-TEST%' 
     ORDER BY time DESC LIMIT 3;"
EOF

echo ""
echo "Recent AOS weather readings:"
ssh -i ~/dev/th-lab01.pem ubuntu@$EC2_HOST << 'EOF'
  docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -c \
    "SELECT time, station_id, temperature_c, rainfall_mm, humidity_pct 
     FROM aos_weather_data 
     WHERE station_id = 'AOS-001' 
     ORDER BY time DESC LIMIT 3;"
EOF

echo ""
echo "✅ Testing complete!"