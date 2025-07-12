#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================"
echo -e "Testing Munbon Microservices"
echo -e "======================================${NC}"

# Function to test endpoint
test_endpoint() {
    local method=$1
    local url=$2
    local headers=$3
    local data=$4
    local expected=$5
    local description=$6
    
    echo -e "\n${YELLOW}Testing: $description${NC}"
    echo "  URL: $url"
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" $headers "$url")
    else
        response=$(curl -s -w "\n%{http_code}" -X $method $headers -d "$data" "$url")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "$expected" ]; then
        echo -e "  ${GREEN}✓ Success (HTTP $http_code)${NC}"
        if [ ! -z "$body" ]; then
            echo "  Response: $(echo $body | jq -c . 2>/dev/null || echo $body)"
        fi
    else
        echo -e "  ${RED}✗ Failed (HTTP $http_code, expected $expected)${NC}"
        echo "  Response: $body"
    fi
}

# 1. Test GIS Service
echo -e "\n${BLUE}1. Testing GIS Service${NC}"
echo "====================="

# Health check
test_endpoint "GET" \
    "http://localhost:3007/health" \
    "" \
    "" \
    "200" \
    "GIS Health Check"

# Get zones
test_endpoint "GET" \
    "http://localhost:3007/api/v1/gis/zones" \
    "-H 'Accept: application/json'" \
    "" \
    "200" \
    "Get Irrigation Zones"

# Get parcels
test_endpoint "GET" \
    "http://localhost:3007/api/v1/gis/parcels?limit=5" \
    "-H 'Accept: application/json'" \
    "" \
    "200" \
    "Get Agricultural Parcels"

# 2. Test Sensor Data Service
echo -e "\n${BLUE}2. Testing Sensor Data Service${NC}"
echo "=============================="

# Health check
test_endpoint "GET" \
    "http://localhost:3000/health" \
    "" \
    "" \
    "200" \
    "Sensor Data Health Check"

# Test water level ingestion
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
test_endpoint "POST" \
    "http://localhost:3000/api/v1/telemetry/water-level" \
    "-H 'Authorization: Bearer munbon-ridr-water-level' -H 'Content-Type: application/json'" \
    "{\"stationId\":\"WL_TEST_001\",\"timestamp\":\"$timestamp\",\"waterLevel\":5.23,\"unit\":\"meters\"}" \
    "201" \
    "Ingest Water Level Data"

# Test moisture ingestion
test_endpoint "POST" \
    "http://localhost:3000/api/v1/telemetry/moisture" \
    "-H 'Authorization: Bearer munbon-m2m-moisture' -H 'Content-Type: application/json'" \
    "{\"deviceId\":\"MOISTURE_TEST_001\",\"timestamp\":\"$timestamp\",\"moisture\":65.5,\"temperature\":28.3,\"humidity\":72.1}" \
    "201" \
    "Ingest Moisture Data"

# 3. Test External API
echo -e "\n${BLUE}3. Testing External Data API${NC}"
echo "============================"

# Get water level data
test_endpoint "GET" \
    "http://localhost:3000/api/v1/external/water-level?limit=5" \
    "-H 'X-API-Key: rid-ms-dev-1234567890abcdef'" \
    "" \
    "200" \
    "Query Water Level Data (External API)"

# Get moisture data
test_endpoint "GET" \
    "http://localhost:3000/api/v1/external/moisture?limit=5" \
    "-H 'X-API-Key: test-key-fedcba0987654321'" \
    "" \
    "200" \
    "Query Moisture Data (External API)"

# 4. Test Authentication
echo -e "\n${BLUE}4. Testing Authentication${NC}"
echo "========================"

# Test invalid token
test_endpoint "POST" \
    "http://localhost:3000/api/v1/telemetry/water-level" \
    "-H 'Authorization: Bearer invalid-token' -H 'Content-Type: application/json'" \
    "{\"stationId\":\"WL001\",\"timestamp\":\"$timestamp\",\"waterLevel\":5.23}" \
    "401" \
    "Invalid Bearer Token (Should Fail)"

# Test invalid API key
test_endpoint "GET" \
    "http://localhost:3000/api/v1/external/water-level" \
    "-H 'X-API-Key: invalid-api-key'" \
    "" \
    "401" \
    "Invalid API Key (Should Fail)"

# 5. Summary
echo -e "\n${BLUE}======================================"
echo -e "Test Summary"
echo -e "======================================${NC}"

echo -e "\n${YELLOW}Service URLs:${NC}"
echo "  - GIS Service: http://localhost:3007"
echo "  - Sensor Data Service: http://localhost:3000"

echo -e "\n${YELLOW}Test Tokens:${NC}"
echo "  - Water Level: munbon-ridr-water-level"
echo "  - Moisture: munbon-m2m-moisture"
echo "  - External API: rid-ms-dev-1234567890abcdef"

echo -e "\n${YELLOW}AWS Endpoints:${NC}"
echo "  - Shape Upload: https://6wls4auo90.execute-api.ap-southeast-1.amazonaws.com/dev/api/v1/gis/shapefile/upload"
echo "  - Public API: https://munbon-api.ridms.dev"

echo -e "\n${GREEN}Testing complete!${NC}"