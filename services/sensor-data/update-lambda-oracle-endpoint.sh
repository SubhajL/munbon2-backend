#!/bin/bash

# Update AWS Lambda to use Oracle Cloud endpoint
set -e

# Configuration
LAMBDA_FUNCTION_NAME="munbon-sensor-handler"
AWS_REGION="ap-southeast-1"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}======================================"
echo "Update Lambda to Oracle Cloud Endpoint"
echo "======================================${NC}"

# Get Oracle instance IP
if [ -z "$ORACLE_INSTANCE_IP" ]; then
    echo -e "${YELLOW}Enter your Oracle Cloud instance IP:${NC}"
    read -p "IP Address: " ORACLE_INSTANCE_IP
fi

# Get internal API key
if [ -z "$INTERNAL_API_KEY" ]; then
    INTERNAL_API_KEY="munbon-internal-f3b89263126548"
    echo -e "${YELLOW}Using default internal API key: $INTERNAL_API_KEY${NC}"
fi

# Test Oracle endpoint first
echo -e "${YELLOW}Testing Oracle Cloud endpoint...${NC}"
HEALTH_CHECK=$(curl -s -w "\n%{http_code}" http://$ORACLE_INSTANCE_IP:3000/health 2>/dev/null | tail -1)

if [ "$HEALTH_CHECK" != "200" ]; then
    echo -e "${RED}Error: Oracle Cloud endpoint is not responding correctly${NC}"
    echo "Please ensure the unified API is running on Oracle Cloud instance"
    exit 1
fi

echo -e "${GREEN}✓ Oracle Cloud endpoint is healthy${NC}"

# Get current Lambda configuration
echo -e "${YELLOW}Getting current Lambda configuration...${NC}"
CURRENT_ENV=$(aws lambda get-function-configuration \
    --function-name $LAMBDA_FUNCTION_NAME \
    --region $AWS_REGION \
    --query 'Environment.Variables' \
    --output json 2>/dev/null || echo "{}")

echo "Current environment variables:"
echo $CURRENT_ENV | jq .

# Update Lambda environment variables
echo -e "${YELLOW}Updating Lambda environment variables...${NC}"

# Build new environment variables
NEW_ENV=$(echo $CURRENT_ENV | jq --arg url "http://$ORACLE_INSTANCE_IP:3000" --arg key "$INTERNAL_API_KEY" \
    '. + {UNIFIED_API_URL: $url, INTERNAL_API_KEY: $key}')

# Update Lambda
aws lambda update-function-configuration \
    --function-name $LAMBDA_FUNCTION_NAME \
    --region $AWS_REGION \
    --environment "Variables=$NEW_ENV" \
    --output json > /dev/null

echo -e "${GREEN}✓ Lambda configuration updated${NC}"

# Wait for update to complete
echo -e "${YELLOW}Waiting for Lambda update to complete...${NC}"
sleep 10

# Test Lambda endpoint
echo -e "${YELLOW}Testing Lambda endpoint...${NC}"
TEST_RESPONSE=$(curl -s -X GET "https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/api/v1/sensors/water-level/latest" \
    -H "x-api-key: test-key-123" \
    -w "\n%{http_code}" 2>/dev/null | tail -1)

if [ "$TEST_RESPONSE" == "200" ] || [ "$TEST_RESPONSE" == "403" ]; then
    echo -e "${GREEN}✓ Lambda is responding correctly${NC}"
else
    echo -e "${YELLOW}Warning: Lambda returned status code $TEST_RESPONSE${NC}"
fi

# Create test script
cat > test-oracle-integration.sh << EOF
#!/bin/bash

# Test script for Oracle Cloud integration

echo "Testing Oracle Cloud Unified API directly..."
curl -s -X GET http://$ORACLE_INSTANCE_IP:3000/api/v1/sensors/water-level/latest \\
    -H "x-internal-key: $INTERNAL_API_KEY" | jq .

echo -e "\nTesting through AWS Lambda..."
curl -s -X GET https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com/api/v1/sensors/water-level/latest \\
    -H "x-api-key: test-key-123" | jq .
EOF

chmod +x test-oracle-integration.sh

echo -e "\n${GREEN}======================================"
echo "Lambda Update Complete!"
echo "======================================"
echo "Oracle Cloud Endpoint: http://$ORACLE_INSTANCE_IP:3000"
echo "Lambda Function: $LAMBDA_FUNCTION_NAME"
echo "Region: $AWS_REGION"
echo ""
echo "Test the integration:"
echo "./test-oracle-integration.sh"
echo ""
echo "View Lambda logs:"
echo "aws logs tail /aws/lambda/$LAMBDA_FUNCTION_NAME --follow --region $AWS_REGION"
echo "======================================${NC}"