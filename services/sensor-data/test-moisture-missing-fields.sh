#!/bin/bash

# Test moisture endpoint with missing fields
# Ensures graceful handling of incomplete data

echo "🧪 Testing moisture endpoint with missing fields..."

ENDPOINT="http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture"

# Test 1: Minimal data with missing GPS and some sensor fields
echo "📋 Test 1: Minimal valid data"
MINIMAL_DATA='{
  "gw_id": "5",
  "gateway_date": "2025/08/02",
  "gateway_utc": "07:00:00",
  "sensor": [
    {
      "sensor_id": "20",
      "sensor_date": "2025/08/02",
      "sensor_utc": "07:00:00",
      "humid_hi": "10",
      "humid_low": "8"
    }
  ]
}'

curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: text/plain" \
  -d "$MINIMAL_DATA" | jq .

echo ""
echo "📋 Test 2: Gateway only (no sensor array)"
GATEWAY_ONLY='{
  "gw_id": "6",
  "gateway_date": "2025/08/02",
  "gateway_utc": "07:01:00",
  "gps_lat": "13.94551",
  "gps_lng": "100.73405",
  "gw_temp": "35.5",
  "gw_batt": "12.5"
}'

curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: text/plain" \
  -d "$GATEWAY_ONLY" | jq .

echo ""
echo "📋 Test 3: Empty sensor array"
EMPTY_SENSORS='{
  "gw_id": "7",
  "gateway_date": "2025/08/02",
  "gateway_utc": "07:02:00",
  "sensor": []
}'

curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: text/plain" \
  -d "$EMPTY_SENSORS" | jq .

echo ""
echo "📋 Test 4: Completely empty payload"
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: text/plain" \
  -d "" | jq .

echo ""
echo "📋 Test 5: Invalid JSON"
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: text/plain" \
  -d "not valid json" | jq .

echo ""
echo "✅ All test cases completed"