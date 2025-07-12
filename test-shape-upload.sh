#!/bin/bash

echo "Testing SHAPE File Upload with correct format..."
echo "================================================"

# Create a test zip file
echo "Test shapefile data" > test_shape.txt
zip -q test_shape.zip test_shape.txt

# Test 1: Try the upload endpoint directly (might work without auth)
echo -e "\nTest 1: Upload without Authorization header"
curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/rid-ms/upload \
  -F "file=@test_shape.zip" \
  -F "waterDemandMethod=RID-MS" \
  -F "processingInterval=weekly" \
  -F "zone=TestZone" \
  -s -w "\nHTTP Status: %{http_code}\n\n"

# Test 2: Try with Bearer token format
echo -e "\nTest 2: Upload with Bearer token"
curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/rid-ms/upload \
  -H "Authorization: Bearer munbon-ridms-shape" \
  -F "file=@test_shape.zip" \
  -F "waterDemandMethod=RID-MS" \
  -s -w "\nHTTP Status: %{http_code}\n\n"

# Test 3: Check if the endpoint exists
echo -e "\nTest 3: OPTIONS request to check CORS"
curl -X OPTIONS https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/rid-ms/upload \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -s -w "\nHTTP Status: %{http_code}\n\n"

# Test 4: Try telemetry endpoint with shape token to see if it's accepted
echo -e "\nTest 4: Test shape token on telemetry endpoint"
curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridms-shape/telemetry \
  -H "Content-Type: application/json" \
  -d '{"type": "shape-file", "test": true}' \
  -s -w "\nHTTP Status: %{http_code}\n\n"

# Clean up
rm -f test_shape.txt test_shape.zip

echo "Tests complete!"