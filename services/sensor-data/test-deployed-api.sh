#!/bin/bash

# Test script for deployed Munbon Public Data API

# Configuration
API_GATEWAY_ID="26ikiexzlc"
STAGE="dev"
BASE_URL="https://${API_GATEWAY_ID}.execute-api.ap-southeast-1.amazonaws.com/${STAGE}/api/v1/public"

# Test API Keys (replace with actual keys from environment)
API_KEY="rid-ms-prod-1234567890abcdef"  # Replace with actual key

# Get today's date in Buddhist calendar
YEAR_CE=$(date +%Y)
YEAR_BE=$((YEAR_CE + 543))
TODAY_BE=$(date +%d/%m/)$YEAR_BE

echo "=== Testing Deployed Munbon Public API ==="
echo "API Gateway ID: $API_GATEWAY_ID"
echo "Base URL: $BASE_URL"
echo "Test Date: $TODAY_BE (Buddhist calendar)"
echo ""

# Function to test endpoint
test_endpoint() {
    local endpoint=$1
    local description=$2
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Testing: $description"
    echo "URL: $BASE_URL$endpoint"
    echo ""
    
    # Make request with timing
    start_time=$(date +%s.%N)
    response=$(curl -s -w "\nHTTP_STATUS:%{http_code}\nTIME_TOTAL:%{time_total}" \
        -H "X-API-Key: $API_KEY" \
        "$BASE_URL$endpoint")
    end_time=$(date +%s.%N)
    
    http_code=$(echo "$response" | grep "HTTP_STATUS:" | cut -d: -f2)
    time_total=$(echo "$response" | grep "TIME_TOTAL:" | cut -d: -f2)
    body=$(echo "$response" | sed '/HTTP_STATUS:/d' | sed '/TIME_TOTAL:/d')
    
    if [ "$http_code" = "200" ]; then
        echo "✅ Success (HTTP $http_code) - Response time: ${time_total}s"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
    else
        echo "❌ Failed (HTTP $http_code)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
    fi
    echo ""
}

# Test authentication first
echo "=== AUTHENTICATION TEST ==="
echo "Testing with no API key (should fail)..."
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$BASE_URL/water-levels/latest")
http_code=$(echo "$response" | grep "HTTP_STATUS:" | cut -d: -f2)
if [ "$http_code" = "401" ]; then
    echo "✅ Correctly rejected (HTTP 401)"
else
    echo "⚠️  Unexpected response (HTTP $http_code)"
fi
echo ""

# Test each endpoint
echo "=== WATER LEVEL ENDPOINTS ==="
test_endpoint "/water-levels/latest" "Latest water level readings"
test_endpoint "/water-levels/timeseries?date=$TODAY_BE" "Water level time series for today"
test_endpoint "/water-levels/statistics?date=$TODAY_BE" "Water level statistics for today"

echo "=== MOISTURE ENDPOINTS ==="
test_endpoint "/moisture/latest" "Latest moisture readings"
test_endpoint "/moisture/timeseries?date=$TODAY_BE" "Moisture time series for today"
test_endpoint "/moisture/statistics?date=$TODAY_BE" "Moisture statistics for today"

echo "=== AOS/WEATHER ENDPOINTS ==="
test_endpoint "/aos/latest" "Latest AOS/weather data"
test_endpoint "/aos/timeseries?date=$TODAY_BE" "AOS time series for today"
test_endpoint "/aos/statistics?date=$TODAY_BE" "AOS statistics for today"

# Test error cases
echo "=== ERROR HANDLING TESTS ==="
test_endpoint "/water-levels/timeseries" "Missing date parameter (should fail with 400)"
test_endpoint "/water-levels/timeseries?date=invalid" "Invalid date format (should fail)"

# Performance summary
echo "=== DEPLOYMENT SUMMARY ==="
echo "✅ API Gateway ID: $API_GATEWAY_ID"
echo "✅ Region: ap-southeast-1"
echo "✅ Stage: $STAGE"
echo "✅ Total endpoints: 9 data + 1 CORS"
echo ""
echo "Full API documentation available at:"
echo "$BASE_URL/../../../ (when Swagger UI is configured)"
echo ""
echo "To use in production:"
echo "1. Replace test API key with production keys"
echo "2. Configure database connection in Lambda environment"
echo "3. Set up monitoring with CloudWatch"
echo "4. Configure custom domain (optional)"