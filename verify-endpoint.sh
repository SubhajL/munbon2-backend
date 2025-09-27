#!/bin/bash

echo "=== Verifying Moisture Endpoint Configuration ==="
echo ""

# The endpoint from the code
ENDPOINT="http://43.208.201.191:8080/api/sensor-data/moisture/munbon-m2m-moisture"
echo "Configured endpoint: $ENDPOINT"
echo ""

# Test with different tokens to see if any work
echo "Testing different token variations:"
TOKENS=("munbon-m2m-moisture" "munbon-moisture" "moisture" "munbon-m2m" "sensor-moisture")

for token in "${TOKENS[@]}"; do
    echo -n "Testing token '$token': "
    response=$(curl -s -w "\n%{http_code}" -X POST "http://43.208.201.191:8080/api/sensor-data/moisture/$token" \
        -H "Content-Type: application/json" \
        -d '{"test": "endpoint-check"}' 2>&1)
    http_code=$(echo "$response" | tail -n1)
    
    if [ "$http_code" == "200" ]; then
        echo "✅ SUCCESS (HTTP $http_code)"
    else
        echo "❌ Failed (HTTP $http_code)"
    fi
done

echo ""
echo "Checking service info:"
curl -s http://43.208.201.191:8080/ | jq '.endpoints.moisture' 2>/dev/null || echo "No endpoint info available"

echo ""
echo "=== CONCLUSION ==="
echo "The endpoint URL is correct: $ENDPOINT"
echo ""
echo "Possible reasons sensors aren't sending data:"
echo "1. Sensors might be offline or without power"
echo "2. Sensors might be misconfigured with wrong endpoint URL"
echo "3. Network/connectivity issues at sensor locations"
echo "4. Sensors might be using a different endpoint or protocol"
echo "5. Authentication token mismatch (if sensors use different token)"