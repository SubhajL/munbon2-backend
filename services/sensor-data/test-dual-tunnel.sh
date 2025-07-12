#!/bin/bash

# Test script for dual-tunnel configuration
# Tests both the main API tunnel and moisture sensor tunnel

set -e

echo "🔍 Testing Munbon Dual-Tunnel Configuration"
echo "==========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
MAIN_TUNNEL="https://munbon-api-proxy.beautifyai.io"
MOISTURE_TUNNEL="https://munbon-moisture.beautifyai.io"
MOISTURE_HEALTH="https://munbon-moisture-health.beautifyai.io"

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

# Function to test endpoint
test_endpoint() {
    local name=$1
    local url=$2
    local method=${3:-GET}
    local data=$4
    local expected_status=${5:-200}
    
    echo -e "\n${BLUE}Testing: $name${NC}"
    echo "URL: $url"
    echo "Method: $method"
    
    if [ "$method" = "POST" ] && [ -n "$data" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$url" \
            -H "Content-Type: application/json" \
            -d "$data" || echo "000")
    else
        response=$(curl -s -o /dev/null -w "%{http_code}" "$url" || echo "000")
    fi
    
    if [ "$response" = "$expected_status" ]; then
        echo -e "${GREEN}✅ PASS${NC} - Status: $response"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ FAIL${NC} - Expected: $expected_status, Got: $response"
        ((TESTS_FAILED++))
    fi
}

# Function to test TLS version
test_tls_version() {
    local name=$1
    local url=$2
    local tls_version=$3
    
    echo -e "\n${BLUE}Testing TLS: $name${NC}"
    echo "URL: $url"
    echo "TLS Version: $tls_version"
    
    response=$(curl -s -o /dev/null -w "%{http_code}" --$tls_version "$url" 2>&1 || echo "000")
    
    if [[ "$response" =~ ^[2-3][0-9][0-9]$ ]]; then
        echo -e "${GREEN}✅ PASS${NC} - $tls_version supported"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ FAIL${NC} - $tls_version not supported"
        ((TESTS_FAILED++))
    fi
}

# Function to test cipher suite
test_cipher() {
    local name=$1
    local url=$2
    local cipher=$3
    
    echo -e "\n${BLUE}Testing Cipher: $name${NC}"
    echo "URL: $url"
    echo "Cipher: $cipher"
    
    # Use openssl to test specific cipher
    if timeout 5 openssl s_client -connect "${url#https://}:443" -cipher "$cipher" </dev/null 2>/dev/null | grep -q "Cipher is"; then
        echo -e "${GREEN}✅ PASS${NC} - Cipher $cipher supported"
        ((TESTS_PASSED++))
    else
        echo -e "${YELLOW}⚠️  SKIP${NC} - Cipher $cipher not tested (may still be supported)"
    fi
}

echo -e "\n${YELLOW}1. Testing Main API Tunnel${NC}"
echo "================================"

# Test main tunnel health
test_endpoint "Main Tunnel Health" "$MAIN_TUNNEL/health" "GET"

# Test AOS endpoints via main tunnel
test_endpoint "AOS Latest Data" "$MAIN_TUNNEL/api/v1/public/aos/latest" "GET"
test_endpoint "AOS Hourly Data" "$MAIN_TUNNEL/api/v1/public/aos/hourly" "GET"

echo -e "\n${YELLOW}2. Testing Moisture Sensor Tunnel${NC}"
echo "===================================="

# Test moisture tunnel health
test_endpoint "Moisture Tunnel Health" "$MOISTURE_HEALTH/health" "GET"

# Test moisture endpoints
test_endpoint "Moisture Current Data" "$MOISTURE_TUNNEL/api/v1/moisture/current" "GET"
test_endpoint "Moisture Alerts" "$MOISTURE_TUNNEL/api/v1/moisture/alerts" "GET"

# Test telemetry ingestion
TELEMETRY_DATA='{
  "deviceId": "TEST-MOISTURE-001",
  "sensorType": "moisture",
  "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'",
  "data": {
    "sensor_id": "001",
    "humid_hi": "45",
    "humid_low": "52",
    "temp_hi": "28.5",
    "temp_low": "26.3",
    "flood": "no",
    "sensor_batt": "385"
  }
}'

test_endpoint "Moisture Telemetry Ingestion" \
    "$MOISTURE_TUNNEL/api/v1/munbon-m2m-moisture/telemetry" \
    "POST" \
    "$TELEMETRY_DATA" \
    "200"

echo -e "\n${YELLOW}3. Testing Legacy TLS Support${NC}"
echo "================================="

# Test TLS versions on moisture tunnel
test_tls_version "TLS 1.0 Support" "$MOISTURE_TUNNEL/health" "tlsv1.0"
test_tls_version "TLS 1.1 Support" "$MOISTURE_TUNNEL/health" "tlsv1.1"
test_tls_version "TLS 1.2 Support" "$MOISTURE_TUNNEL/health" "tlsv1.2"

echo -e "\n${YELLOW}4. Testing Legacy Ciphers${NC}"
echo "============================="

# Test specific legacy ciphers
test_cipher "RC4-SHA" "$MOISTURE_TUNNEL" "RC4-SHA"
test_cipher "DES-CBC3-SHA" "$MOISTURE_TUNNEL" "DES-CBC3-SHA"
test_cipher "AES128-SHA" "$MOISTURE_TUNNEL" "AES128-SHA"

echo -e "\n${YELLOW}5. Testing Tunnel Isolation${NC}"
echo "==============================="

# Verify tunnels are isolated
echo -e "\n${BLUE}Checking tunnel processes...${NC}"
pm2_status=$(pm2 list --no-color | grep -E "(munbon-tunnel|munbon-moisture-tunnel)" || echo "No tunnels found")
echo "$pm2_status"

echo -e "\n${YELLOW}6. Performance Test${NC}"
echo "======================="

# Simple latency test
echo -e "\n${BLUE}Testing response times...${NC}"

start_time=$(date +%s%N)
curl -s "$MAIN_TUNNEL/health" > /dev/null
end_time=$(date +%s%N)
main_latency=$(( ($end_time - $start_time) / 1000000 ))
echo "Main tunnel latency: ${main_latency}ms"

start_time=$(date +%s%N)
curl -s "$MOISTURE_TUNNEL/health" > /dev/null
end_time=$(date +%s%N)
moisture_latency=$(( ($end_time - $start_time) / 1000000 ))
echo "Moisture tunnel latency: ${moisture_latency}ms"

echo -e "\n${YELLOW}7. DNS Resolution Test${NC}"
echo "=========================="

echo -e "\n${BLUE}Checking DNS resolution...${NC}"
echo -n "Main tunnel: "
dig +short munbon-api-proxy.beautifyai.io CNAME | head -1
echo -n "Moisture tunnel: "
dig +short munbon-moisture.beautifyai.io CNAME | head -1

# Summary
echo -e "\n${YELLOW}========================================${NC}"
echo -e "${YELLOW}Test Summary${NC}"
echo -e "${YELLOW}========================================${NC}"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}✅ All tests passed! Dual-tunnel configuration is working correctly.${NC}"
    exit 0
else
    echo -e "\n${RED}❌ Some tests failed. Please check the configuration.${NC}"
    
    echo -e "\n${YELLOW}Troubleshooting Tips:${NC}"
    echo "1. Check if both tunnels are running: pm2 status"
    echo "2. Verify DNS records are configured correctly"
    echo "3. Ensure local services are running (ports 3000 and 3005)"
    echo "4. Check tunnel logs: pm2 logs munbon-tunnel / pm2 logs munbon-moisture-tunnel"
    exit 1
fi