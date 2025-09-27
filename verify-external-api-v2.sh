#!/bin/bash

# Munbon External API V2.0 Verification Script
# Production endpoint verification

echo "🔍 Munbon External API V2.0 Verification"
echo "========================================"
echo ""

# Configuration
PROD_BASE_URL="https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/prod/api/v1"
API_KEY="rid-ms-prod-key1"

# Get current date in Buddhist calendar format
CURRENT_YEAR=$(($(date +%Y) + 543))
CURRENT_DATE=$(date "+%d/%m/$CURRENT_YEAR")

echo "📅 Current Date (Buddhist): $CURRENT_DATE"
echo "🔑 Using API Key: $API_KEY"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to test endpoint
test_endpoint() {
    local endpoint=$1
    local description=$2
    local query_params=$3
    
    echo -e "${YELLOW}Testing: $description${NC}"
    echo "Endpoint: $endpoint$query_params"
    
    RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
        -H "X-API-Key: $API_KEY" \
        "$PROD_BASE_URL$endpoint$query_params" 2>&1)
    
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
}

# Test Water Level Endpoints
echo "=== 💧 WATER LEVEL DATA API ==="
echo ""

test_endpoint "/public/water-levels/latest" "Latest Water Level Data" ""

test_endpoint "/public/water-levels/timeseries" "Water Level Time Series" "?date=$CURRENT_DATE"

test_endpoint "/public/water-levels/statistics" "Water Level Statistics" "?date=$CURRENT_DATE"

# Test Moisture Endpoints
echo "=== 🌱 MOISTURE DATA API ==="
echo ""

test_endpoint "/public/moisture/latest" "Latest Moisture Data" ""

test_endpoint "/public/moisture/timeseries" "Moisture Time Series" "?date=$CURRENT_DATE"

test_endpoint "/public/moisture/statistics" "Moisture Statistics" "?date=$CURRENT_DATE"

# Test AOS Meteorological Endpoints
echo "=== 🌤️ AOS METEOROLOGICAL DATA API ==="
echo ""

test_endpoint "/public/aos/latest" "Latest AOS Data" ""

test_endpoint "/public/aos/timeseries" "AOS Time Series" "?date=$CURRENT_DATE"

test_endpoint "/public/aos/statistics" "AOS Statistics" "?date=$CURRENT_DATE"

# Summary
echo ""
echo "=== 📊 VERIFICATION SUMMARY ==="
echo ""
echo "🔗 Production Base URL: $PROD_BASE_URL"
echo "🔐 API Key Used: $API_KEY"
echo "📅 Test Date: $CURRENT_DATE"
echo ""
echo "💡 Notes:"
echo "  - Active water level sensors: AWD-B75A, AWD-B6B5, AWD-B8A4, AWD-B33B, AWD-B7E6, AWD-B9BE"
echo "  - Date format: Buddhist calendar (DD/MM/YYYY where YYYY = CE + 543)"
echo "  - Flow rate is currently 0 (no flow meters installed at most gates)"
echo ""
echo "✅ Verification complete!"