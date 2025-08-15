#!/bin/bash

# Test enhanced moisture endpoint with new JSON format
# Uses the exact format provided by the user

echo "🧪 Testing enhanced moisture endpoint with new JSON format..."

# Server endpoint
ENDPOINT="http://43.209.22.250:8080/api/sensor-data/moisture/munbon-m2m-moisture"

# Test data - exact format from user
MOISTURE_DATA='{
  "gw_id": "3",
  "gateway_msg_type": "Interval",
  "gateway_date": "2025/08/02",
  "gateway_utc": "06:54:14",
  "gps_lat": "13.94551",
  "gps_lng": "100.73405",
  "gw_temp": "37.10",
  "gw_himid": "43.40",
  "gw_head_index": "42.87",
  "gw_batt": "12.33",
  "sensor": [
    {
      "sensor_id": "13",
      "sensor_msg_type": "Interval",
      "sensor_date": "2025/08/02",
      "sensor_utc": "06:51:17",
      "humid_hi": "008",
      "humid_low": "006",
      "temp_hi": "29.00",
      "temp_low": "29.50",
      "amb_humid": "33.7",
      "amb_temp": "38.2",
      "flood": "no",
      "sensor_batt": "404"
    },
    {
      "sensor_id": "13",
      "sensor_msg_type": "Interval",
      "sensor_date": "2025/08/02",
      "sensor_utc": "06:52:24",
      "humid_hi": "008",
      "humid_low": "006",
      "temp_hi": "28.50",
      "temp_low": "29.50",
      "amb_humid": "33.6",
      "amb_temp": "38.3",
      "flood": "no",
      "sensor_batt": "404"
    },
    {
      "sensor_id": "13",
      "sensor_msg_type": "Interval",
      "sensor_date": "2025/08/02",
      "sensor_utc": "06:53:31",
      "humid_hi": "008",
      "humid_low": "006",
      "temp_hi": "29.00",
      "temp_low": "29.50",
      "amb_humid": "34.2",
      "amb_temp": "38.3",
      "flood": "no",
      "sensor_batt": "404"
    }
  ]
}'

echo "📡 Sending moisture data with Content-Type: text/plain..."
echo ""

# Send with text/plain content type (as sensors do)
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$ENDPOINT" \
  -H "Content-Type: text/plain" \
  -H "User-Agent: QUECTEL_MODULE" \
  -d "$MOISTURE_DATA")

HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | head -n -1)

echo "📥 Response:"
echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
echo ""
echo "📊 HTTP Status: $HTTP_CODE"

if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ Success! Data accepted"
  
  # Check statistics
  echo ""
  echo "📈 Checking server statistics..."
  curl -s http://43.209.22.250:8080/api/stats | jq .
  
  # Check if data reached SQS
  echo ""
  echo "🔍 Checking SQS queue..."
  AWS_REGION=ap-southeast-1 aws sqs get-queue-attributes \
    --queue-url https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue \
    --attribute-names ApproximateNumberOfMessages \
    --query "Attributes.ApproximateNumberOfMessages" \
    --output text 2>/dev/null || echo "Unable to check SQS"
    
else
  echo "❌ Failed with status $HTTP_CODE"
fi

echo ""
echo "💡 To check server logs:"
echo "   ssh -i ~/dev/th-lab01.pem ubuntu@43.209.22.250 'pm2 logs moisture-http --lines 50'"