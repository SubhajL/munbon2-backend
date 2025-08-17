#!/bin/bash

# Test Port Access Script for ROS/GIS Integration Service

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

HOST="${EC2_HOST:-43.208.201.191}"
PORT="3022"

echo -e "${GREEN}Testing ROS/GIS Integration Service Access${NC}"
echo ""

# Test 1: Check if port is open using nc (netcat)
echo "Test 1: Checking if port ${PORT} is open..."
if nc -zv -w5 ${HOST} ${PORT} 2>&1 | grep -q "succeeded\|connected"; then
    echo -e "${GREEN}✓ Port ${PORT} is open and accessible${NC}"
    PORT_OPEN=true
else
    echo -e "${RED}✗ Port ${PORT} is not accessible from outside${NC}"
    PORT_OPEN=false
fi

# Test 2: Try to access health endpoint
echo ""
echo "Test 2: Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s -m 5 http://${HOST}:${PORT}/health 2>&1)
CURL_EXIT_CODE=$?

if [ ${CURL_EXIT_CODE} -eq 0 ] && echo "${HEALTH_RESPONSE}" | grep -q "healthy"; then
    echo -e "${GREEN}✓ Health endpoint is accessible${NC}"
    echo "${HEALTH_RESPONSE}" | python3 -m json.tool 2>/dev/null || echo "${HEALTH_RESPONSE}"
    SERVICE_ACCESSIBLE=true
else
    echo -e "${RED}✗ Cannot access health endpoint${NC}"
    if [ ${CURL_EXIT_CODE} -eq 7 ]; then
        echo "   Connection refused or timed out"
    elif [ ${CURL_EXIT_CODE} -eq 28 ]; then
        echo "   Connection timed out"
    else
        echo "   Error: ${HEALTH_RESPONSE}"
    fi
    SERVICE_ACCESSIBLE=false
fi

# Test 3: Check from the server itself
echo ""
echo "Test 3: Testing internal access (from the server)..."
INTERNAL_CHECK=$(ssh -i ~/dev/th-lab01.pem ubuntu@${HOST} "curl -s http://localhost:${PORT}/health | python3 -m json.tool" 2>/dev/null)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Service is running correctly internally${NC}"
    INTERNAL_OK=true
else
    echo -e "${RED}✗ Service is not accessible internally${NC}"
    INTERNAL_OK=false
fi

# Summary and recommendations
echo ""
echo "================================"
echo -e "${YELLOW}SUMMARY${NC}"
echo "================================"

if [ "${INTERNAL_OK}" = true ] && [ "${SERVICE_ACCESSIBLE}" = false ]; then
    echo -e "${YELLOW}The service is running correctly but is not accessible from outside.${NC}"
    echo ""
    echo "This indicates a firewall/security group issue. To fix this:"
    echo ""
    echo "1. ${GREEN}AWS EC2 Security Group Update:${NC}"
    echo "   - Log into AWS Console"
    echo "   - Navigate to EC2 → Instances"
    echo "   - Find instance with IP ${HOST}"
    echo "   - Click on Security tab → Security groups"
    echo "   - Edit inbound rules"
    echo "   - Add rule: Type=Custom TCP, Port=${PORT}, Source=0.0.0.0/0"
    echo ""
    echo "2. ${GREEN}Alternative Cloud Provider:${NC}"
    echo "   - If not AWS, check your cloud provider's firewall settings"
    echo "   - Look for 'Security Groups', 'Firewall Rules', or 'Network Security'"
    echo "   - Add inbound rule for TCP port ${PORT}"
    echo ""
    echo "3. ${GREEN}Local Firewall (if applicable):${NC}"
    echo "   Run on the server:"
    echo "   sudo ufw allow ${PORT}/tcp"
    echo "   sudo ufw reload"
elif [ "${SERVICE_ACCESSIBLE}" = true ]; then
    echo -e "${GREEN}✓ Service is fully accessible!${NC}"
    echo ""
    echo "You can access the service at:"
    echo "- Health: http://${HOST}:${PORT}/health"
    echo "- GraphQL: http://${HOST}:${PORT}/graphql"
else
    echo -e "${RED}Service appears to be down or not running${NC}"
    echo ""
    echo "Check the Docker container:"
    echo "ssh -i ~/dev/th-lab01.pem ubuntu@${HOST} 'docker ps | grep ros-gis-integration'"
fi