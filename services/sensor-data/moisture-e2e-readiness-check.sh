#!/bin/bash

echo "🔍 Moisture Sensor E2E Readiness Check"
echo "======================================"

# 1. Check Cloudflare Tunnel Status
echo -e "\n1️⃣ Cloudflare Tunnel Status:"
pm2 list | grep moisture-tunnel
echo -n "   Tunnel Health: "
curl -s -o /dev/null -w "%{http_code}" https://munbon-moisture.beautifyai.io/health

# 2. Check Sensor Data Service
echo -e "\n\n2️⃣ Sensor Data Service Status:"
pm2 list | grep sensor-data
echo -n "   API Health: "
curl -s http://localhost:3003/health | jq -r '.status' 2>/dev/null || echo "Not responding"

# 3. Check Legacy TLS Support
echo -e "\n3️⃣ Legacy TLS/Cipher Support:"
echo -n "   TLS 1.0: "
curl -s --tlsv1.0 --tls-max 1.0 https://munbon-moisture.beautifyai.io/health -o /dev/null -w "%{http_code}" 2>&1 | grep -q "200" && echo "✅ Supported" || echo "❌ Not supported"

echo -n "   TLS 1.1: "
curl -s --tlsv1.1 --tls-max 1.1 https://munbon-moisture.beautifyai.io/health -o /dev/null -w "%{http_code}" 2>&1 | grep -q "200" && echo "✅ Supported" || echo "❌ Not supported"

# 4. Check Database Tables
echo -e "\n4️⃣ Database Tables:"
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
SELECT 
    'sensor_registry' as table_name,
    COUNT(*) filter (where sensor_type = 'moisture') as moisture_sensors,
    COUNT(*) filter (where sensor_type = 'moisture' AND last_seen > NOW() - INTERVAL '1 hour') as active_last_hour
FROM sensor_registry
UNION ALL
SELECT 
    'moisture_readings' as table_name,
    COUNT(DISTINCT sensor_id) as moisture_sensors,
    COUNT(*) filter (where time > NOW() - INTERVAL '1 hour') as active_last_hour
FROM moisture_readings;
"

# 5. Check API Endpoints
echo -e "\n5️⃣ API Endpoints Test:"
echo -n "   POST /api/v1/munbon-m2m-moisture/telemetry: "
RESPONSE=$(curl -s -X POST https://munbon-moisture.beautifyai.io/api/v1/munbon-m2m-moisture/telemetry \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-test-munbon" \
  -d '{
    "deviceId": "E2E-TEST-001",
    "sensorType": "moisture",
    "sensorId": "99999-99999",
    "macAddress": "99:99:99:99:99:99",
    "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")'",
    "version": "2.0",
    "data": {
      "humid_hi": 50.0,
      "humid_low": 60.0,
      "temp_hi": 25.0,
      "temp_low": 24.0,
      "ambient_humid": 70.0,
      "ambient_temp": 28.0,
      "flood": 0,
      "voltage": 12.6
    },
    "location": {
      "lat": 14.8794,
      "lng": 104.8606
    },
    "signalStrength": -70,
    "batteryLevel": 90
  }' -w "\nHTTP Status: %{http_code}")

echo "$RESPONSE" | grep -q "200" && echo "✅ Working" || echo "❌ Failed"

echo -n "   GET /api/v1/moisture: "
curl -s http://localhost:3003/api/v1/moisture?limit=1 -o /dev/null -w "%{http_code}" | grep -q "200" && echo "✅ Working" || echo "❌ Failed"

echo -n "   GET /api/v1/sensors (moisture): "
curl -s "http://localhost:3003/api/v1/sensors?type=moisture&limit=1" -o /dev/null -w "%{http_code}" | grep -q "200" && echo "✅ Working" || echo "❌ Failed"

# 6. Check Data Flow
echo -e "\n6️⃣ Data Flow Verification:"
echo "   Checking if E2E test sensor was registered..."
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -t -c "
SELECT CASE 
    WHEN EXISTS (SELECT 1 FROM sensor_registry WHERE sensor_id = '99999-99999')
    THEN '✅ Auto-registration working'
    ELSE '❌ Auto-registration failed'
END;
"

echo "   Checking if E2E test data was stored..."
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -t -c "
SELECT CASE 
    WHEN EXISTS (SELECT 1 FROM moisture_readings WHERE sensor_id = '99999-99999' AND time > NOW() - INTERVAL '1 minute')
    THEN '✅ Data storage working'
    ELSE '❌ Data storage failed'
END;
"

# 7. Check Multi-layer Support
echo -e "\n7️⃣ Multi-layer Moisture Support:"
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
SELECT 
    'Surface (10cm)' as layer,
    COUNT(*) filter (where moisture_surface_pct IS NOT NULL) as readings,
    ROUND(AVG(moisture_surface_pct)::numeric, 2) as avg_moisture
FROM moisture_readings
WHERE time > NOW() - INTERVAL '1 hour'
UNION ALL
SELECT 
    'Deep (30cm+)' as layer,
    COUNT(*) filter (where moisture_deep_pct IS NOT NULL) as readings,
    ROUND(AVG(moisture_deep_pct)::numeric, 2) as avg_moisture
FROM moisture_readings
WHERE time > NOW() - INTERVAL '1 hour';
"

# 8. Cleanup test sensor
echo -e "\n8️⃣ Cleaning up test data..."
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
DELETE FROM moisture_readings WHERE sensor_id = '99999-99999';
DELETE FROM sensor_readings WHERE sensor_id = '99999-99999';
DELETE FROM sensor_registry WHERE sensor_id = '99999-99999';
"

echo -e "\n✅ E2E Readiness Check Complete!"
echo "================================="