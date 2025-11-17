#!/bin/bash

echo "Testing if HTTP 8080 accepts gateway 0001 data"
echo "================================================"
echo ""

EC2_HOST="43.208.201.191"
ENDPOINT="http://${EC2_HOST}:8080/api/sensor-data/moisture/munbon-m2m-moisture"

echo "1. Testing Gateway 0001 with real sensor data"
echo "-----------------------------------------------------------"
RESPONSE_0001=$(curl -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -w "\nHTTP_CODE:%{http_code}" \
  -d '{
    "gw_id": "0001",
    "latitude": "13.7563",
    "longitude": "100.5018",
    "sensor": [{
      "sensor_id": "0007",
      "humid_hi": "45",
      "humid_low": "68",
      "temp_hi": "31.5",
      "temp_low": "29.8",
      "amb_humid": "65.2",
      "amb_temp": "32.1",
      "flood": "no",
      "sensor_batt": "395"
    }]
  }' 2>&1)

echo "$RESPONSE_0001"
HTTP_CODE_0001=$(echo "$RESPONSE_0001" | grep "HTTP_CODE:" | cut -d: -f2)

echo ""
echo ""
echo "2. Verifying the data was written to database"
echo "-----------------------------------------------------------"
sleep 2
PGPASSWORD='__ROTATED_DB_PASSWORD__' psql -h 43.208.201.191 -U postgres -d sensor_data -c "
SELECT 
  sensor_id,
  time,
  moisture_surface_pct as surface,
  moisture_deep_pct as deep,
  voltage
FROM moisture_readings 
WHERE sensor_id = '0001-0007'
  AND time > NOW() - INTERVAL '1 minute'
ORDER BY time DESC
LIMIT 3;
"

echo ""
echo "3. Testing Gateway 0002 for comparison"
echo "-----------------------------------------------------------"
RESPONSE_0002=$(curl -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -w "\nHTTP_CODE:%{http_code}" \
  -d '{
    "gw_id": "0002",
    "latitude": "13.7563",
    "longitude": "100.5018",
    "sensor": [{
      "sensor_id": "0001",
      "humid_hi": "50",
      "humid_low": "72",
      "temp_hi": "28.5",
      "temp_low": "27.0",
      "amb_humid": "60.0",
      "amb_temp": "35.0",
      "flood": "no",
      "sensor_batt": "400"
    }]
  }' 2>&1)

echo "$RESPONSE_0002"
HTTP_CODE_0002=$(echo "$RESPONSE_0002" | grep "HTTP_CODE:" | cut -d: -f2)

echo ""
echo ""
echo "4. Verifying Gateway 0002 data"
echo "-----------------------------------------------------------"
sleep 2
PGPASSWORD='__ROTATED_DB_PASSWORD__' psql -h 43.208.201.191 -U postgres -d sensor_data -c "
SELECT 
  sensor_id,
  time,
  moisture_surface_pct as surface,
  moisture_deep_pct as deep,
  voltage
FROM moisture_readings 
WHERE sensor_id = '0002-0001'
  AND time > NOW() - INTERVAL '1 minute'
ORDER BY time DESC
LIMIT 3;
"

echo ""
echo "5. Testing Gateway 0001 with sensor_id 0000 (like 0002 currently sends)"
echo "-----------------------------------------------------------"
RESPONSE_0001_0000=$(curl -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -w "\nHTTP_CODE:%{http_code}" \
  -d '{
    "gw_id": "0001",
    "latitude": "13.7563",
    "longitude": "100.5018",
    "sensor": [{
      "sensor_id": "0000",
      "humid_hi": "",
      "humid_low": "",
      "temp_hi": "",
      "temp_low": "",
      "amb_humid": "",
      "amb_temp": "",
      "flood": "no",
      "sensor_batt": ""
    }]
  }' 2>&1)

echo "$RESPONSE_0001_0000"

echo ""
echo ""
echo "6. Check if 0001-0000 was written"
echo "-----------------------------------------------------------"
sleep 2
PGPASSWORD='__ROTATED_DB_PASSWORD__' psql -h 43.208.201.191 -U postgres -d sensor_data -c "
SELECT 
  sensor_id,
  time,
  moisture_surface_pct as surface,
  moisture_deep_pct as deep
FROM moisture_readings 
WHERE sensor_id = '0001-0000'
  AND time > NOW() - INTERVAL '1 minute'
ORDER BY time DESC
LIMIT 3;
"

echo ""
echo "================================================"
echo "TEST RESULTS SUMMARY"
echo "================================================"
echo ""
echo "Gateway 0001 with sensor 0007: HTTP $HTTP_CODE_0001"
echo "Gateway 0002 with sensor 0001: HTTP $HTTP_CODE_0002"
echo ""

if [ "$HTTP_CODE_0001" = "200" ] && [ "$HTTP_CODE_0002" = "200" ]; then
    echo "✅ CONCLUSION: Both gateways accepted by HTTP service"
    echo "✅ No filtering on gateway 0001 in the code"
    echo ""
    echo "⚠️  Gateway 0001 hardware has PHYSICALLY STOPPED transmitting"
    echo ""
    echo "ACTION REQUIRED:"
    echo "  - Check gateway 0001 power supply"
    echo "  - Verify network connectivity"
    echo "  - Inspect physical device for LED indicators"
else
    echo "❌ Unexpected: One or both requests failed"
    echo "   This would indicate a service or network issue"
fi

echo ""
