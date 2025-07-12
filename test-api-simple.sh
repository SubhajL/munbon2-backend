#!/bin/bash

echo "Testing Munbon API Endpoints"
echo "============================"

# Test SHAPE file upload (without actual file)
echo -e "\n1. SHAPE File Upload Endpoint:"
curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/rid-ms/upload \
  -H "Authorization: Bearer munbon-ridms-shape" \
  -H "Content-Type: multipart/form-data" \
  -s -w "\nStatus: %{http_code}\n"

# Test water level telemetry
echo -e "\n2. Water Level Telemetry:"
curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/telemetry \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}' \
  -s -w "\nStatus: %{http_code}\n"

# Test moisture telemetry (we know this works)
echo -e "\n3. Moisture Telemetry:"
curl -X POST https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/telemetry \
  -H "Content-Type: application/json" \
  -d '{"gateway_id": "test"}' \
  -s -w "\nStatus: %{http_code}\n"

# Test attributes endpoints
echo -e "\n4. Attributes Endpoints:"
curl -s https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-ridr-water-level/attributes
echo ""
curl -s https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/munbon-m2m-moisture/attributes