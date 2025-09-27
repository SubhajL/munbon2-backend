#!/bin/bash

EC2_HOST="43.208.201.191"

echo "=== Checking Moisture Data Services on EC2 ==="
echo ""

echo "1. Services on port 8080 (Ingestion):"
curl -s http://${EC2_HOST}:8080/health | jq '.'
echo ""

echo "2. Available endpoints on port 8080:"
curl -s http://${EC2_HOST}:8080/ | jq '.'
echo ""

echo "3. Testing moisture data submission:"
curl -X POST http://${EC2_HOST}:8080/api/sensor-data/moisture/munbon-m2m-moisture \
  -H "Content-Type: application/json" \
  -d '{
    "gw_id": "check-test-001",
    "sensor": [{
      "sensor_id": "1",
      "humid_hi": "75",
      "humid_low": "68",
      "temp_hi": "31.5",
      "temp_low": "29.8",
      "amb_humid": "65.2",
      "amb_temp": "32.1",
      "flood": "no"
    }]
  }' 2>&1 | jq '.'

echo ""
echo "=== ISSUE IDENTIFIED ==="
echo "The EC2 deployment (port 8080) is running the simple ingestion-only service."
echo "This service can receive moisture data but CANNOT query it."
echo ""
echo "The full API with query endpoints (/api/v1/sensors/moisture/latest) exists in:"
echo "- unified-api.js (should run on port 8081)"
echo "- moisture.routes.ts (part of the full sensor-data API)"
echo ""
echo "To check moisture data, you need to either:"
echo "1. Deploy the unified-api.js to EC2 (port 8081)"
echo "2. Deploy the full sensor-data API with moisture routes"
echo "3. Access the PostgreSQL database directly"