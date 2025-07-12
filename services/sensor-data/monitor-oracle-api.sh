#!/bin/bash

# Monitor Oracle Cloud Unified API
set -e

# Configuration
ORACLE_IP="${ORACLE_INSTANCE_IP:-}"
INTERNAL_API_KEY="${INTERNAL_API_KEY:-munbon-internal-f3b89263126548}"
CHECK_INTERVAL=30  # seconds

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if IP is provided
if [ -z "$ORACLE_IP" ]; then
    echo -e "${YELLOW}Enter Oracle Cloud instance IP:${NC}"
    read -p "IP: " ORACLE_IP
fi

clear
echo -e "${BLUE}======================================"
echo "Oracle Cloud API Monitor"
echo "Target: http://$ORACLE_IP:3000"
echo "======================================${NC}"

# Function to check endpoint
check_endpoint() {
    local endpoint=$1
    local name=$2
    
    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "x-internal-key: $INTERNAL_API_KEY" \
        "http://$ORACLE_IP:3000$endpoint" 2>/dev/null || echo "000")
    
    if [ "$response" == "200" ]; then
        echo -e "${GREEN}✓ $name: OK${NC}"
    else
        echo -e "${RED}✗ $name: Error (HTTP $response)${NC}"
    fi
}

# Function to get stats
get_stats() {
    # Get water level sensor count
    water_count=$(curl -s -H "x-internal-key: $INTERNAL_API_KEY" \
        "http://$ORACLE_IP:3000/api/v1/sensors/water-level/latest" 2>/dev/null | \
        jq -r '.sensor_count // 0')
    
    # Get moisture sensor count
    moisture_count=$(curl -s -H "x-internal-key: $INTERNAL_API_KEY" \
        "http://$ORACLE_IP:3000/api/v1/sensors/moisture/latest" 2>/dev/null | \
        jq -r '.sensor_count // 0')
    
    echo -e "${BLUE}Active Sensors:${NC}"
    echo "  Water Level: $water_count"
    echo "  Moisture: $moisture_count"
}

# Main monitoring loop
while true; do
    clear
    echo -e "${BLUE}======================================"
    echo "Oracle Cloud API Monitor"
    echo "Time: $(date)"
    echo "======================================${NC}"
    echo
    
    # Check endpoints
    echo -e "${YELLOW}Endpoint Status:${NC}"
    check_endpoint "/health" "Health Check"
    check_endpoint "/api/v1/sensors/water-level/latest" "Water Level API"
    check_endpoint "/api/v1/sensors/moisture/latest" "Moisture API"
    check_endpoint "/api/v1/sensors/aos/latest" "AOS Weather API"
    echo
    
    # Get statistics
    get_stats
    echo
    
    # Check Lambda integration
    echo -e "${YELLOW}Lambda Integration:${NC}"
    lambda_response=$(curl -s -o /dev/null -w "%{http_code}" \
        "https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/health" 2>/dev/null || echo "000")
    
    if [ "$lambda_response" == "200" ]; then
        echo -e "${GREEN}✓ AWS Lambda: Connected${NC}"
    else
        echo -e "${RED}✗ AWS Lambda: Error (HTTP $lambda_response)${NC}"
    fi
    echo
    
    echo -e "${BLUE}Refreshing in $CHECK_INTERVAL seconds... (Ctrl+C to exit)${NC}"
    sleep $CHECK_INTERVAL
done