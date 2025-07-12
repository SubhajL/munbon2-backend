#!/bin/bash

echo "🌱 Testing new moisture sensor auto-registration..."

# Test with a completely new sensor
echo "📡 Sending data from new moisture sensor..."

curl -s -X POST https://munbon-moisture.beautifyai.io/api/v1/munbon-m2m-moisture/telemetry \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-test-munbon" \
  -d '{
    "deviceId": "MOIST-NEW-002",
    "sensorType": "moisture",
    "sensorId": "00003-00001",
    "macAddress": "00:00:00:00:03:01",
    "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")'",
    "version": "2.0",
    "data": {
      "humid_hi": 42.5,
      "humid_low": 58.7,
      "temp_hi": 29.2,
      "temp_low": 27.8,
      "ambient_humid": 82.1,
      "ambient_temp": 33.5,
      "flood": 0,
      "voltage": 12.9
    },
    "location": {
      "lat": 14.8793,
      "lng": 104.8605
    },
    "signalStrength": -72,
    "batteryLevel": 92
  }' | jq '.'

echo -e "\n✅ Checking new sensor registration..."

docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
SELECT 
    sensor_id, 
    sensor_type, 
    manufacturer, 
    is_active, 
    last_seen,
    metadata->>'deviceId' as device_id,
    metadata->>'macAddress' as mac_address
FROM sensor_registry 
WHERE sensor_type = 'moisture'
ORDER BY created_at DESC 
LIMIT 5;
"

echo -e "\n📊 Moisture sensor summary..."
docker exec munbon-timescaledb psql -U postgres -d munbon_timescale -c "
SELECT 
    COUNT(DISTINCT sr.sensor_id) as total_moisture_sensors,
    COUNT(DISTINCT CASE WHEN sr.last_seen > NOW() - INTERVAL '1 hour' THEN sr.sensor_id END) as active_last_hour,
    COUNT(mr.*) as total_readings,
    MAX(mr.time) as latest_reading
FROM sensor_registry sr
LEFT JOIN moisture_readings mr ON sr.sensor_id = mr.sensor_id
WHERE sr.sensor_type = 'moisture';
"