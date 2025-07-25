#!/bin/bash

# Test the complete data flow after updates

echo "=== Testing Complete Data Flow ==="
echo ""
echo "This script will test:"
echo "1. Data ingestion (sensor → Lambda → SQS → Consumer → EC2 DB)"
echo "2. Data exposure (External API → Lambda → EC2 DB)"
echo "3. Cloudflare tunnel (Moisture sensor → EC2)"
echo ""

# Configuration
API_GATEWAY_BASE="https://5e3l647kpd.execute-api.ap-southeast-1.amazonaws.com"
EC2_HOST="43.209.12.182"
TUNNEL_URL="https://munbon-api.br-firewall-breath-planner.trycloudflare.com"

# Test colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print test results
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
    else
        echo -e "${RED}❌ $2${NC}"
    fi
}

# Function to test endpoint
test_endpoint() {
    local url=$1
    local description=$2
    local headers=$3
    
    echo -n "Testing $description... "
    
    if [ -n "$headers" ]; then
        response=$(curl -s -o /dev/null -w "%{http_code}" -H "$headers" "$url" 2>/dev/null)
    else
        response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
    fi
    
    if [ "$response" = "200" ] || [ "$response" = "201" ]; then
        print_result 0 "HTTP $response"
        return 0
    else
        print_result 1 "HTTP $response"
        return 1
    fi
}

echo "=== 1. Testing EC2 Services ==="
echo ""

# Test PostgreSQL on EC2
echo -n "Testing PostgreSQL connection on EC2... "
nc -zv $EC2_HOST 5432 2>/dev/null
print_result $? "PostgreSQL (5432)"

# Test Sensor Data Service
test_endpoint "http://$EC2_HOST:3001/health" "Sensor Data Service"

# Test Consumer Dashboard
test_endpoint "http://$EC2_HOST:3002" "Consumer Dashboard"

echo ""
echo "=== 2. Testing Data Ingestion Flow ==="
echo ""

# Test water level sensor ingestion
echo "Sending test water level data..."
WATER_LEVEL_RESPONSE=$(curl -s -X POST \
  "$API_GATEWAY_BASE/dev/api/v1/munbon-test-devices/telemetry" \
  -H "Content-Type: application/json" \
  -d '{
    "deviceID": "test-device-'$(date +%s)'",
    "macAddress": "AA:BB:CC:DD:EE:FF",
    "latitude": 13.7563,
    "longitude": 100.5018,
    "RSSI": -65,
    "voltage": 420,
    "level": 25,
    "timestamp": '$(date +%s)'000
  }' 2>/dev/null)

if echo "$WATER_LEVEL_RESPONSE" | grep -q "queued"; then
    print_result 0 "Water level data ingestion"
else
    print_result 1 "Water level data ingestion"
    echo "Response: $WATER_LEVEL_RESPONSE"
fi

# Test moisture sensor via Cloudflare tunnel
echo ""
echo "Testing moisture sensor via Cloudflare tunnel..."
if [ -n "$TUNNEL_URL" ]; then
    MOISTURE_RESPONSE=$(curl -s -X POST \
      "$TUNNEL_URL/api/v1/munbon-m2m-moisture/telemetry" \
      -H "Content-Type: application/json" \
      -d '{
        "gateway_id": "test-gw-001",
        "msg_type": "interval",
        "date": "'$(date +%Y/%m/%d)'",
        "time": "'$(date +%H:%M:%S)'",
        "latitude": "13.7563",
        "longitude": "100.5018",
        "gw_batt": "372",
        "sensor": [{
          "sensor_id": "test-sensor-001",
          "flood": "no",
          "amb_humid": "65",
          "amb_temp": "28.5",
          "humid_hi": "45",
          "temp_hi": "26.0",
          "humid_low": "70",
          "temp_low": "24.5",
          "sensor_batt": "395"
        }]
      }' 2>/dev/null)
    
    if echo "$MOISTURE_RESPONSE" | grep -q "success\|queued\|received"; then
        print_result 0 "Moisture data via tunnel"
    else
        print_result 1 "Moisture data via tunnel"
        echo "Response: $MOISTURE_RESPONSE"
    fi
else
    echo -e "${YELLOW}⚠️  Cloudflare tunnel URL not configured${NC}"
fi

echo ""
echo "=== 3. Testing Data Exposure API ==="
echo ""

# Test external API endpoints
API_KEY="test-key-123"

# Test water level latest
test_endpoint "$API_GATEWAY_BASE/prod/api/v1/water-level/latest" \
    "Water Level Latest API" \
    "X-API-Key: $API_KEY"

# Test moisture latest
test_endpoint "$API_GATEWAY_BASE/prod/api/v1/moisture/latest" \
    "Moisture Latest API" \
    "X-API-Key: $API_KEY"

# Test AOS latest
test_endpoint "$API_GATEWAY_BASE/prod/api/v1/aos/latest" \
    "AOS Latest API" \
    "X-API-Key: $API_KEY"

echo ""
echo "=== 4. Testing Database Content ==="
echo ""

# Check if data is being stored in EC2 database
echo "Checking recent sensor data in database..."
RECENT_DATA=$(curl -s "http://$EC2_HOST:3002/api/recent?limit=5" 2>/dev/null)

if echo "$RECENT_DATA" | grep -q "sensorId"; then
    COUNT=$(echo "$RECENT_DATA" | grep -o "sensorId" | wc -l)
    print_result 0 "Found $COUNT recent sensor readings"
else
    print_result 1 "No recent sensor data found"
fi

# Check sensor statistics
echo ""
echo "Checking sensor statistics..."
STATS=$(curl -s "http://$EC2_HOST:3002/api/stats" 2>/dev/null)

if echo "$STATS" | grep -q "messagesReceived"; then
    MESSAGES=$(echo "$STATS" | grep -o '"messagesReceived":[0-9]*' | cut -d: -f2)
    SENSORS=$(echo "$STATS" | grep -o '"sensorCount":[0-9]*' | cut -d: -f2)
    echo -e "${GREEN}✅ Total messages: $MESSAGES, Active sensors: $SENSORS${NC}"
else
    print_result 1 "Could not retrieve statistics"
fi

echo ""
echo "=== 5. Testing SQS Queue ==="
echo ""

# Check SQS queue status
echo "Checking SQS queue messages..."
SQS_ATTRS=$(aws sqs get-queue-attributes \
    --queue-url "https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue" \
    --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
    --region ap-southeast-1 2>/dev/null)

if [ $? -eq 0 ]; then
    VISIBLE=$(echo "$SQS_ATTRS" | grep -o '"ApproximateNumberOfMessages": "[0-9]*"' | cut -d'"' -f4)
    IN_FLIGHT=$(echo "$SQS_ATTRS" | grep -o '"ApproximateNumberOfMessagesNotVisible": "[0-9]*"' | cut -d'"' -f4)
    echo -e "${GREEN}✅ SQS Queue - Visible: ${VISIBLE:-0}, In-flight: ${IN_FLIGHT:-0}${NC}"
else
    print_result 1 "Could not check SQS queue"
fi

echo ""
echo "=== Test Summary ==="
echo ""
echo "If all tests passed:"
echo "✅ Data ingestion is working (Sensors → Lambda → SQS → EC2)"
echo "✅ Data exposure is working (External API → Lambda → EC2)"
echo "✅ Services are running on EC2"
echo ""
echo "If some tests failed:"
echo "1. Check EC2 security group allows required ports"
echo "2. Ensure services are deployed and running on EC2"
echo "3. Verify PostgreSQL is accepting connections"
echo "4. Check CloudFlare tunnel is pointing to correct EC2 endpoint"
echo ""
echo "Logs and debugging:"
echo "- Consumer logs: http://$EC2_HOST:3002"
echo "- Lambda logs: AWS CloudWatch Logs"
echo "- EC2 service logs: docker logs <container-name>"