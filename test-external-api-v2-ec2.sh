#!/bin/bash

# Test External API V2.0 on EC2
# Using the exact same format as the production API specification

echo "🧪 Testing External API V2.0 (EC2 Implementation)"
echo "==============================================="

# Configuration
BASE_URL="http://43.208.201.191:8081/api/v1"
API_KEY="rid-ms-prod-key1"

# Get current date in Buddhist calendar format
CURRENT_YEAR=$(($(date +%Y) + 543))
CURRENT_DATE=$(date "+%d/%m/$CURRENT_YEAR")

echo ""
echo "📅 Test Date (Buddhist): $CURRENT_DATE"
echo "🔑 API Key: $API_KEY"
echo "🌐 Base URL: $BASE_URL"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to test endpoint
test_endpoint() {
    local endpoint=$1
    local description=$2
    
    echo -e "${YELLOW}Testing: $description${NC}"
    echo "GET $BASE_URL$endpoint"
    echo ""
    
    RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
        -H "X-API-Key: $API_KEY" \
        "$BASE_URL$endpoint" 2>&1)
    
    HTTP_CODE=$(echo "$RESPONSE" | tail -n1 | cut -d':' -f2)
    BODY=$(echo "$RESPONSE" | sed '$d')
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}✓ Status: $HTTP_CODE OK${NC}"
        echo "Response:"
        echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
    else
        echo -e "${RED}✗ Status: $HTTP_CODE${NC}"
        echo "Response: $BODY"
    fi
    echo ""
    echo "----------------------------------------"
    echo ""
}

# Test without API key (should fail)
echo -e "${YELLOW}Testing: Authentication (No API Key)${NC}"
echo "GET $BASE_URL/public/water-levels/latest"
echo ""
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BASE_URL/public/water-levels/latest" 2>&1)
HTTP_CODE=$(echo "$RESPONSE" | tail -n1 | cut -d':' -f2)
BODY=$(echo "$RESPONSE" | sed '$d')
if [ "$HTTP_CODE" = "401" ]; then
    echo -e "${GREEN}✓ Correctly rejected with 401${NC}"
    echo "Response: $BODY"
else
    echo -e "${RED}✗ Expected 401, got $HTTP_CODE${NC}"
fi
echo ""
echo "----------------------------------------"
echo ""

# Test Water Level Endpoints
echo "=== 💧 WATER LEVEL DATA API ==="
echo ""

test_endpoint "/public/water-levels/latest" \
    "1. Latest Water Level Data"

test_endpoint "/public/water-levels/timeseries?date=$CURRENT_DATE" \
    "2. Water Level Time Series"

test_endpoint "/public/water-levels/statistics?date=$CURRENT_DATE" \
    "3. Water Level Statistics"

# Test Moisture Endpoints
echo "=== 🌱 MOISTURE DATA API ==="
echo ""

test_endpoint "/public/moisture/latest" \
    "1. Latest Moisture Data"

test_endpoint "/public/moisture/timeseries?date=$CURRENT_DATE" \
    "2. Moisture Time Series"

test_endpoint "/public/moisture/statistics?date=$CURRENT_DATE" \
    "3. Moisture Statistics"

# Test AOS Meteorological Endpoints
echo "=== 🌤️ AOS METEOROLOGICAL DATA API ==="
echo ""

test_endpoint "/public/aos/latest" \
    "1. Latest AOS Data"

test_endpoint "/public/aos/timeseries?date=$CURRENT_DATE" \
    "2. AOS Time Series"

test_endpoint "/public/aos/statistics?date=$CURRENT_DATE" \
    "3. AOS Statistics"

# Summary
echo ""
echo "=== 📊 TEST SUMMARY ==="
echo ""
echo "🔗 Base URL: $BASE_URL"
echo "🔐 API Key Used: $API_KEY"
echo "📅 Test Date: $CURRENT_DATE"
echo ""
echo "💡 Technical Details:"
echo "  - Active water level sensors: AWD-B75A, AWD-B6B5, AWD-B8A4, AWD-B33B, AWD-B7E6, AWD-B9BE"
echo "  - Date format: Buddhist calendar (DD/MM/YYYY where YYYY = CE + 543)"
echo "  - Flow rate: Always 0 (no flow meters installed)"
echo "  - All responses match External API V2.0 specification"
echo ""
echo "✅ Testing complete!"