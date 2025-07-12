#!/bin/bash

# Script to register moisture sensor in sensor_registry table
# This must be done before sending any sensor readings

echo "Registering moisture sensor in sensor_registry..."

# Database connection details
DB_HOST="localhost"
DB_PORT="5433"
DB_NAME="munbon_timescale"
DB_USER="munbon_user"
export PGPASSWORD="munbon_password"

# Sensor details
SENSOR_ID="00002-00003"
SENSOR_TYPE="moisture"
MANUFACTURER="M2M"

# SQL command to insert sensor
SQL="INSERT INTO sensor_registry (
    sensor_id, 
    sensor_type, 
    manufacturer, 
    location_lat, 
    location_lng, 
    last_seen, 
    metadata,
    is_active
) VALUES (
    '$SENSOR_ID',
    '$SENSOR_TYPE',
    '$MANUFACTURER',
    14.8794,
    104.8606,
    CURRENT_TIMESTAMP,
    '{ \"macAddress\": \"00:00:00:00:00:03\", \"deviceId\": \"MOIST-TEST-001\", \"model\": \"M2M-MOISTURE-V2\" }'::jsonb,
    true
) ON CONFLICT (sensor_id) 
DO UPDATE SET
    last_seen = CURRENT_TIMESTAMP,
    location_lat = EXCLUDED.location_lat,
    location_lng = EXCLUDED.location_lng,
    metadata = sensor_registry.metadata || EXCLUDED.metadata,
    updated_at = CURRENT_TIMESTAMP;"

# Execute SQL
psql -h $DB_HOST -p $DB_PORT -d $DB_NAME -U $DB_USER -c "$SQL"

if [ $? -eq 0 ]; then
    echo "✅ Sensor registered successfully!"
    
    # Verify registration
    echo -e "\nVerifying sensor registration:"
    psql -h $DB_HOST -p $DB_PORT -d $DB_NAME -U $DB_USER -c "SELECT sensor_id, sensor_type, manufacturer, is_active, last_seen FROM sensor_registry WHERE sensor_id = '$SENSOR_ID';"
else
    echo "❌ Failed to register sensor"
    exit 1
fi

# Now test moisture data submission through tunnel
echo -e "\n📡 Testing moisture data submission through tunnel..."

curl -X POST https://munbon-moisture.beautifyai.io/api/v1/munbon-m2m-moisture/telemetry \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-test-munbon" \
  -d '{
    "deviceId": "MOIST-TEST-001",
    "sensorType": "moisture",
    "sensorId": "00002-00003",
    "macAddress": "00:00:00:00:00:03",
    "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")'",
    "version": "2.0",
    "data": {
      "humid_hi": 65.5,
      "humid_low": 72.3,
      "temp_hi": 28.4,
      "temp_low": 26.8,
      "ambient_humid": 78.2,
      "ambient_temp": 32.1,
      "flood": 0,
      "voltage": 12.8
    },
    "location": {
      "lat": 14.8794,
      "lng": 104.8606
    },
    "signalStrength": -67,
    "batteryLevel": 85
  }' -w "\n"

echo -e "\n📊 Checking if data was inserted into moisture_readings table..."
sleep 2

# Check moisture_readings table
psql -h $DB_HOST -p $DB_PORT -d $DB_NAME -U $DB_USER -c "SELECT time, sensor_id, moisture_surface_pct, moisture_deep_pct, flood_status FROM moisture_readings WHERE sensor_id = '$SENSOR_ID' ORDER BY time DESC LIMIT 5;"

echo -e "\n✨ Script completed!"