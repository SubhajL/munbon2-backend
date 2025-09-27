#!/bin/bash

EC2_HOST="43.208.201.191"
API_KEY="munbon-internal-f3b89263126548"

echo "=== Checking Moisture Sensor Data via API ==="
echo "Timestamp: $(date)"
echo ""

echo "1. Checking service health:"
curl -s http://${EC2_HOST}:8080/health | jq '.' || echo "Failed to get health status"
echo ""

echo "2. Submitting test moisture data:"
TEST_DATA='{
  "gateway_id": "curl-test-001",
  "gw_id": "curl-test-001",
  "latitude": 13.7563,
  "longitude": 100.5018,
  "humid_hi": 65.5,
  "humid_low": 58.2,
  "temp_hi": 30.3,
  "temp_low": 28.1,
  "timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"
}'

echo "Sending to: http://${EC2_HOST}:8080/api/sensor-data/moisture/munbon-m2m-moisture"
curl -X POST http://${EC2_HOST}:8080/api/sensor-data/moisture/munbon-m2m-moisture \
  -H "Content-Type: application/json" \
  -d "$TEST_DATA" | jq '.'

echo ""
echo "3. Checking for recent moisture data in logs:"
echo "(Note: We need SSH access to check actual logs and database)"

echo ""
echo "4. Available endpoints on port 8080:"
# Check root path
curl -s http://${EC2_HOST}:8080/ 2>/dev/null || echo "No response from root path"

echo ""
echo "5. Testing other possible moisture endpoints:"
# Test various endpoints
for endpoint in "/api/moisture" "/api/sensors/moisture" "/api/v1/moisture"; do
    echo -n "Testing GET $endpoint: "
    response=$(curl -s -w "\n%{http_code}" http://${EC2_HOST}:8080${endpoint} -H "x-internal-key: ${API_KEY}" 2>/dev/null)
    http_code=$(echo "$response" | tail -n1)
    echo "HTTP $http_code"
done