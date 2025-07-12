#!/bin/bash

echo "Testing Munbon API Endpoints..."
echo "================================"

API_BASE="https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev"

# Test 1: SHAPE File Upload Endpoint
echo -e "\n1. Testing SHAPE File Upload Endpoint"
echo "-------------------------------------"
echo "URL: $API_BASE/api/v1/rid-ms/upload"

# Create a dummy zip file for testing
echo "Creating test zip file..."
echo "Test shapefile data" > test_shapefile.txt
zip test_shapefile.zip test_shapefile.txt > /dev/null 2>&1

# Test the upload endpoint
curl -X POST "$API_BASE/api/v1/rid-ms/upload" \
  -H "Authorization: Bearer munbon-ridms-shape" \
  -F "file=@test_shapefile.zip" \
  -F "waterDemandMethod=RID-MS" \
  -F "processingInterval=weekly" \
  -F "zone=TestZone" \
  -F "description=Test upload" \
  -w "\nHTTP Status: %{http_code}\n" \
  -s | jq . || echo "Response parsing failed"

# Clean up
rm -f test_shapefile.txt test_shapefile.zip

# Test 2: Water Level Telemetry Endpoint
echo -e "\n\n2. Testing Water Level Telemetry Endpoint"
echo "-------------------------------------------"
echo "URL: $API_BASE/api/v1/munbon-ridr-water-level/telemetry"

curl -X POST "$API_BASE/api/v1/munbon-ridr-water-level/telemetry" \
  -H "Content-Type: application/json" \
  -d '{
    "deviceId": "WL001",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "waterLevel": 5.5,
    "flowRate": 2.3,
    "temperature": 28.5
  }' \
  -w "\nHTTP Status: %{http_code}\n" \
  -s | jq . || echo "Response parsing failed"

# Test 3: Moisture Sensor Telemetry Endpoint
echo -e "\n\n3. Testing Moisture Sensor Telemetry Endpoint"
echo "----------------------------------------------"
echo "URL: $API_BASE/api/v1/munbon-m2m-moisture/telemetry"

curl -X POST "$API_BASE/api/v1/munbon-m2m-moisture/telemetry" \
  -H "Content-Type: application/json" \
  -d '{
    "gateway_id": "00001",
    "msg_type": "interval",
    "date": "'$(date +%Y/%m/%d)'",
    "time": "'$(date +%H:%M:%S)'",
    "latitude": "13.12345",
    "longitude": "100.54621",
    "gw_batt": "372",
    "sensor": [
      {
        "sensor_id": "00001",
        "flood": "no",
        "amb_humid": "60",
        "amb_temp": "40.50",
        "humid_hi": "50",
        "temp_hi": "25.50",
        "humid_low": "72",
        "temp_low": "25.00",
        "sensor_batt": "395"
      }
    ]
  }' \
  -w "\nHTTP Status: %{http_code}\n" \
  -s | jq . || echo "Response parsing failed"

# Test 4: Check Attributes Endpoint
echo -e "\n\n4. Testing Attributes Endpoints"
echo "---------------------------------"

for token in "munbon-ridr-water-level" "munbon-m2m-moisture" "munbon-ridms-shape"; do
  echo -e "\nTesting: $API_BASE/api/v1/$token/attributes"
  curl -X GET "$API_BASE/api/v1/$token/attributes" \
    -w "\nHTTP Status: %{http_code}\n" \
    -s | jq . || echo "Response parsing failed"
done

# Test 5: Check for Data API endpoints
echo -e "\n\n5. Checking for Data Retrieval APIs"
echo "------------------------------------"

# Test public API endpoints (these might require API key)
endpoints=(
  "/api/v1/public/water-levels/latest"
  "/api/v1/public/moisture/latest"
  "/api/v1/public/aos/latest"
  "/api/v1/external/water-levels"
  "/api/v1/external/moisture"
  "/api/v1/water-levels"
  "/api/v1/moisture"
  "/api/v1/sensors/active"
)

for endpoint in "${endpoints[@]}"; do
  echo -e "\nTesting: $API_BASE$endpoint"
  curl -X GET "$API_BASE$endpoint" \
    -H "x-api-key: test-key" \
    -w "\nHTTP Status: %{http_code}\n" \
    -s -m 5 | jq . 2>/dev/null || echo "No response or timeout"
done

echo -e "\n\nEndpoint testing complete!"