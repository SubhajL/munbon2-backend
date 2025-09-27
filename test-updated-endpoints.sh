#!/bin/bash

# Test script for updated Lambda endpoints
# Run this after port 8081 is open and Lambda functions are updated

echo "🧪 Testing Updated Lambda Endpoints"
echo "==================================="
echo ""

# Configuration
API_GATEWAY_BASE="https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1"
EC2_API_BASE="http://43.208.201.191:8081/api/v1"
API_KEY="rid-ms-prod-key1"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test function
test_endpoint() {
    local base_url=$1
    local endpoint=$2
    local description=$3
    
    echo -e "${YELLOW}Testing: $description${NC}"
    echo "URL: $base_url$endpoint"
    
    RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
        -H "x-api-key: $API_KEY" \
        "$base_url$endpoint" 2>&1)
    
    HTTP_CODE=$(echo "$RESPONSE" | tail -n1 | cut -d':' -f2)
    BODY=$(echo "$RESPONSE" | sed '$d')
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✅ Success (HTTP $HTTP_CODE)${NC}"
        echo "Response preview:"
        echo "$BODY" | jq -r 'if type == "object" then . else . end' 2>/dev/null | head -10
    else
        echo -e "${RED}❌ Failed (HTTP $HTTP_CODE)${NC}"
        echo "Response: $BODY"
    fi
    echo "---"
    echo ""
}

# First test EC2 API directly
echo "=== 1. Testing EC2 API Directly (Port 8081) ==="
echo ""

test_endpoint "$EC2_API_BASE" "/public/water-levels/latest" "Water Level Latest (EC2 Direct)"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ EC2 API is not accessible on port 8081${NC}"
    echo "Please ensure:"
    echo "1. Port 8081 is open in the security group"
    echo "2. The External API service is running on EC2"
    echo ""
    echo "Test command:"
    echo "curl -H \"x-api-key: $API_KEY\" $EC2_API_BASE/public/water-levels/latest"
    exit 1
fi

# Then test Lambda endpoints
echo "=== 2. Testing Lambda Endpoints (API Gateway) ==="
echo ""

# Test water level endpoints
echo "--- Water Level Endpoints ---"
test_endpoint "$API_GATEWAY_BASE" "/public/water-levels/latest" "Water Level Latest"
test_endpoint "$API_GATEWAY_BASE" "/public/water-levels/timeseries?date=10/09/2568" "Water Level Timeseries"
test_endpoint "$API_GATEWAY_BASE" "/public/water-levels/statistics?date=10/09/2568" "Water Level Statistics"

# Test moisture endpoints
echo "--- Moisture Endpoints ---"
test_endpoint "$API_GATEWAY_BASE" "/public/moisture/latest" "Moisture Latest"
test_endpoint "$API_GATEWAY_BASE" "/public/moisture/timeseries?date=10/09/2568" "Moisture Timeseries"
test_endpoint "$API_GATEWAY_BASE" "/public/moisture/statistics?date=10/09/2568" "Moisture Statistics"

# Test AOS endpoints
echo "--- AOS Weather Endpoints ---"
test_endpoint "$API_GATEWAY_BASE" "/public/aos/latest" "AOS Latest"
test_endpoint "$API_GATEWAY_BASE" "/public/aos/timeseries?date=15/07/2568" "AOS Timeseries (July data)"
test_endpoint "$API_GATEWAY_BASE" "/public/aos/statistics?date=15/07/2568" "AOS Statistics (July data)"

echo ""
echo "=== Test Summary ==="
echo "If all tests passed, the Lambda → EC2 API proxy is working correctly!"
echo "If tests failed, check:"
echo "1. Port 8081 is open in security group"
echo "2. Lambda functions were updated successfully"
echo "3. EC2 API service is running"
echo ""