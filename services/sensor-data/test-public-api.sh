#!/bin/bash

# Test script for Munbon Public Data APIs

# Configuration
API_KEY="rid-ms-dev-1234567890abcdef"  # Replace with actual API key
BASE_URL="http://localhost:3000/api/v1/public"  # Local testing
# BASE_URL="https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/public"  # AWS Lambda

# Get today's date in Buddhist calendar
TODAY_CE=$(date +%d/%m/%Y)
YEAR_CE=$(date +%Y)
YEAR_BE=$((YEAR_CE + 543))
TODAY_BE=$(date +%d/%m/)$YEAR_BE

echo "=== Munbon Public API Test ==="
echo "Testing with date: $TODAY_BE (Buddhist calendar)"
echo "Base URL: $BASE_URL"
echo ""

# Function to test endpoint
test_endpoint() {
    local endpoint=$1
    local description=$2
    echo "Testing: $description"
    echo "URL: $BASE_URL$endpoint"
    
    response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
        -H "X-API-Key: $API_KEY" \
        "$BASE_URL$endpoint")
    
    http_code=$(echo "$response" | grep "HTTP_STATUS:" | cut -d: -f2)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "200" ]; then
        echo "✅ Success (HTTP $http_code)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
    else
        echo "❌ Failed (HTTP $http_code)"
        echo "$body"
    fi
    echo "---"
    echo ""
}

# Test water level endpoints
echo "=== WATER LEVEL ENDPOINTS ==="
test_endpoint "/water-levels/latest" "Latest water level readings"
test_endpoint "/water-levels/timeseries?date=$TODAY_BE" "Water level time series for today"
test_endpoint "/water-levels/statistics?date=$TODAY_BE" "Water level statistics for today"

# Test moisture endpoints
echo "=== MOISTURE ENDPOINTS ==="
test_endpoint "/moisture/latest" "Latest moisture readings"
test_endpoint "/moisture/timeseries?date=$TODAY_BE" "Moisture time series for today"
test_endpoint "/moisture/statistics?date=$TODAY_BE" "Moisture statistics for today"

# Test AOS/weather endpoints
echo "=== AOS/WEATHER ENDPOINTS ==="
test_endpoint "/aos/latest" "Latest AOS/weather data"
test_endpoint "/aos/timeseries?date=$TODAY_BE" "AOS time series for today"
test_endpoint "/aos/statistics?date=$TODAY_BE" "AOS statistics for today"

# Test error cases
echo "=== ERROR HANDLING ==="
test_endpoint "/water-levels/timeseries" "Missing date parameter (should fail)"

# Test with wrong API key
echo "Testing with invalid API key..."
curl -s -w "\nHTTP_STATUS:%{http_code}" \
    -H "X-API-Key: invalid-key" \
    "$BASE_URL/water-levels/latest" | grep "HTTP_STATUS:" | cut -d: -f2

echo ""
echo "=== Test Complete ==="