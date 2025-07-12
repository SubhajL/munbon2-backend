#!/bin/bash

# Test moisture sensor data
API_URL="https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev"
TOKEN="munbon-m2m-moisture"

# Create test data
DATA='{
  "gateway_id": "00001",
  "msg_type": "interval",
  "date": "'$(date +%Y/%m/%d)'",
  "time": "'$(date +%H:%M:%S)'",
  "latitude": "13.7563",
  "longitude": "100.5018",
  "gw_batt": "372",
  "sensor": [
    {
      "sensor_id": "00001",
      "flood": "no",
      "amb_humid": "65",
      "amb_temp": "32.50",
      "humid_hi": "45",
      "temp_hi": "28.50",
      "humid_low": "58",
      "temp_low": "27.00",
      "sensor_batt": "395"
    }
  ]
}'

echo "🚀 Sending moisture sensor data to AWS Lambda..."
echo "Endpoint: $API_URL/api/v1/$TOKEN/telemetry"
echo ""
echo "Data:"
echo "$DATA" | jq
echo ""

# Send the request
curl -X POST "$API_URL/api/v1/$TOKEN/telemetry" \
  -H "Content-Type: application/json" \
  -d "$DATA" \
  -w "\nHTTP Status: %{http_code}\n"

echo ""
echo "✅ Data sent! Check the consumer dashboard at http://localhost:3002"
echo ""
echo "📊 To verify data in TimescaleDB, run:"
echo "docker exec -it munbon-timescaledb psql -U postgres -d sensor_data -c \"SELECT * FROM sensor.sensors WHERE sensor_id LIKE 'munbon-m2m-%' ORDER BY created_at DESC LIMIT 5;\""