#!/bin/bash

echo "🌱 Testing moisture sensor data with automatic registration..."

# Test moisture data submission through tunnel
echo "📡 Sending moisture data through tunnel..."

RESPONSE=$(curl -s -X POST https://munbon-moisture.beautifyai.io/api/v1/munbon-m2m-moisture/telemetry \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-test-munbon" \
  -d '{
    "deviceId": "MOIST-AUTO-001",
    "sensorType": "moisture",
    "sensorId": "00002-00004",
    "macAddress": "00:00:00:00:00:04",
    "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")'",
    "version": "2.0",
    "data": {
      "humid_hi": 55.8,
      "humid_low": 68.2,
      "temp_hi": 27.5,
      "temp_low": 25.9,
      "ambient_humid": 75.4,
      "ambient_temp": 30.8,
      "flood": 0,
      "voltage": 12.5
    },
    "location": {
      "lat": 14.8795,
      "lng": 104.8607
    },
    "signalStrength": -65,
    "batteryLevel": 88
  }')

echo "Response: $RESPONSE"

# Check if sensor was auto-registered
echo -e "\n📋 Checking sensor registry..."

# Database connection details
DB_HOST="localhost"
DB_PORT="5433"
DB_NAME="munbon_timescale"
DB_USER="munbon_user"
export PGPASSWORD="munbon_password"

psql -h $DB_HOST -p $DB_PORT -d $DB_NAME -U $DB_USER -c "
SELECT 
    sensor_id, 
    sensor_type, 
    manufacturer, 
    is_active, 
    last_seen,
    metadata->>'deviceId' as device_id,
    metadata->>'macAddress' as mac_address,
    metadata->>'version' as version
FROM sensor_registry 
WHERE sensor_id = '00002-00004' 
ORDER BY last_seen DESC 
LIMIT 1;
"

echo -e "\n📊 Checking moisture readings..."
psql -h $DB_HOST -p $DB_PORT -d $DB_NAME -U $DB_USER -c "
SELECT 
    time, 
    sensor_id, 
    moisture_surface_pct, 
    moisture_deep_pct,
    temp_surface_c,
    temp_deep_c,
    ambient_humidity_pct,
    ambient_temp_c,
    flood_status,
    voltage 
FROM moisture_readings 
WHERE sensor_id = '00002-00004' 
ORDER BY time DESC 
LIMIT 5;
"

echo -e "\n✅ Test completed!"