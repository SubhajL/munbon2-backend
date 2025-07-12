#!/bin/bash

# Quick test environment setup using Cloudflare Tunnel
# This provides immediate access without AWS deployment

echo "=== Munbon Test Environment Setup ==="
echo "This will set up a test environment using Cloudflare Tunnel"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if cloudflared is installed
check_cloudflared() {
    if ! command -v cloudflared &> /dev/null; then
        echo -e "${YELLOW}Installing cloudflared...${NC}"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            brew install cloudflare/cloudflare/cloudflared
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
            sudo dpkg -i cloudflared-linux-amd64.deb
            rm cloudflared-linux-amd64.deb
        fi
    fi
}

# Start sensor data service
start_sensor_data() {
    echo "🚀 Starting Sensor Data Service..."
    cd services/sensor-data
    
    # Create test environment file
    cat > .env.test << EOF
NODE_ENV=development
PORT=3001

# Database connections
DB_HOST=localhost
DB_PORT=5433
DB_NAME=sensor_data
DB_USER=postgres
DB_PASSWORD=postgres

# API Keys for testing
EXTERNAL_API_KEYS=test-key-123,rid-ms-test,tmd-test,mobile-test

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
EOF
    
    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo "Installing dependencies..."
        npm install
    fi
    
    # Start the service
    echo "Starting service on port 3001..."
    npm run dev > sensor-data.log 2>&1 &
    SENSOR_PID=$!
    
    cd ../..
    sleep 5
    
    echo -e "${GREEN}✅ Sensor Data Service started (PID: $SENSOR_PID)${NC}"
}

# Start RID-MS service
start_rid_ms() {
    echo "🚀 Starting RID-MS Service..."
    cd services/rid-ms
    
    # Create test environment file
    cat > .env.test << EOF
NODE_ENV=development
PORT=3002

# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rid_ms

# AWS (for local testing with LocalStack)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
S3_BUCKET=munbon-rid-shapefiles

# API Authentication
EXTERNAL_API_TOKEN=munbon-ridms-shape
EOF
    
    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo "Installing dependencies..."
        npm install
    fi
    
    # Build the service
    echo "Building RID-MS..."
    npm run build
    
    # Start the service
    echo "Starting service on port 3002..."
    npm run dev > rid-ms.log 2>&1 &
    RID_PID=$!
    
    cd ../..
    sleep 5
    
    echo -e "${GREEN}✅ RID-MS Service started (PID: $RID_PID)${NC}"
}

# Start Cloudflare tunnels
start_tunnels() {
    echo "🌐 Starting Cloudflare Tunnels..."
    
    # Tunnel for Sensor Data API
    echo "Creating tunnel for Sensor Data API..."
    cloudflared tunnel --url http://localhost:3001 > sensor-tunnel.log 2>&1 &
    SENSOR_TUNNEL_PID=$!
    
    # Tunnel for RID-MS API
    echo "Creating tunnel for RID-MS API..."
    cloudflared tunnel --url http://localhost:3002 > rid-tunnel.log 2>&1 &
    RID_TUNNEL_PID=$!
    
    # Wait for tunnels to establish
    echo "Waiting for tunnels to establish..."
    sleep 10
    
    # Extract URLs
    SENSOR_URL=$(grep -o 'https://.*\.trycloudflare.com' sensor-tunnel.log | head -1)
    RID_URL=$(grep -o 'https://.*\.trycloudflare.com' rid-tunnel.log | head -1)
    
    echo -e "${GREEN}✅ Cloudflare Tunnels established${NC}"
}

# Create test documentation
create_test_docs() {
    cat > test-environment-info.txt << EOF
Munbon Test Environment
=======================
Started: $(date)

🌐 API Endpoints
----------------

Sensor Data API:
$SENSOR_URL
- GET /api/v1/public/water-levels/latest
- GET /api/v1/public/moisture/latest
- GET /api/v1/public/aos/latest

RID-MS API:
$RID_URL
- POST /api/external/shapefile/push
- GET /api/v1/rid-ms/shapefiles
- GET /api/v1/rid-ms/zones/{zone}/parcels

🔑 Test API Keys
----------------
- General: test-key-123
- RID-MS: rid-ms-test
- TMD: tmd-test
- Mobile: mobile-test

📋 Example Commands
-------------------

# Test water levels API
curl -H "X-API-Key: test-key-123" \\
  $SENSOR_URL/api/v1/public/water-levels/latest

# Test moisture data
curl -H "X-API-Key: test-key-123" \\
  "$SENSOR_URL/api/v1/public/moisture/timeseries?date=26/12/2568"

# Upload SHAPE file (base64 encoded ZIP)
curl -X POST \\
  -H "Authorization: Bearer munbon-ridms-shape" \\
  -H "Content-Type: application/json" \\
  -d '{
    "filename": "test_parcels.zip",
    "content": "UEsDBAoAAAAAAIdO4kgAAAAAAAAAAAAAAAAJAAAA...",
    "metadata": {
      "source": "test",
      "zone": "Zone 1"
    }
  }' \\
  $RID_URL/api/external/shapefile/push

# List shape files
curl -H "X-API-Key: test-key-123" \\
  $RID_URL/api/v1/rid-ms/shapefiles

🔧 Service PIDs
---------------
- Sensor Data Service: $SENSOR_PID
- RID-MS Service: $RID_PID
- Sensor Tunnel: $SENSOR_TUNNEL_PID
- RID Tunnel: $RID_TUNNEL_PID

📝 Logs
-------
- Sensor Data: services/sensor-data/sensor-data.log
- RID-MS: services/rid-ms/rid-ms.log
- Sensor Tunnel: sensor-tunnel.log
- RID Tunnel: rid-tunnel.log

⏹️ To Stop Services
-------------------
Run: ./stop-test-environment.sh
EOF

    # Create stop script
    cat > stop-test-environment.sh << EOF
#!/bin/bash

echo "Stopping test environment..."

# Kill services
kill $SENSOR_PID 2>/dev/null
kill $RID_PID 2>/dev/null
kill $SENSOR_TUNNEL_PID 2>/dev/null
kill $RID_TUNNEL_PID 2>/dev/null

# Clean up
rm -f sensor-tunnel.log rid-tunnel.log
rm -f services/sensor-data/sensor-data.log
rm -f services/rid-ms/rid-ms.log

echo "✅ Test environment stopped"
EOF

    chmod +x stop-test-environment.sh
}

# Create API test script
create_api_tests() {
    cat > test-all-endpoints.sh << 'EOF'
#!/bin/bash

# Load test environment info
if [ ! -f test-environment-info.txt ]; then
    echo "❌ test-environment-info.txt not found. Run setup-test-environment.sh first."
    exit 1
fi

# Extract URLs
SENSOR_URL=$(grep -A1 "Sensor Data API:" test-environment-info.txt | tail -1)
RID_URL=$(grep -A1 "RID-MS API:" test-environment-info.txt | tail -1)

echo "=== Testing Munbon APIs ==="
echo ""

# Test function
test_api() {
    local name=$1
    local method=$2
    local url=$3
    local headers=$4
    local data=$5
    
    echo "Testing: $name"
    
    if [ "$method" = "GET" ]; then
        if [ -z "$data" ]; then
            response=$(curl -s -w "\n%{http_code}" $headers "$url")
        else
            response=$(curl -s -w "\n%{http_code}" $headers "$url?$data")
        fi
    else
        response=$(curl -s -w "\n%{http_code}" -X $method $headers -d "$data" "$url")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [[ "$http_code" =~ ^2[0-9][0-9]$ ]]; then
        echo "✅ Success (HTTP $http_code)"
        echo "$body" | jq . 2>/dev/null || echo "$body"
    else
        echo "❌ Failed (HTTP $http_code)"
        echo "$body"
    fi
    echo ""
}

# Test Sensor Data APIs
echo "=== Sensor Data APIs ==="
test_api "Water Levels Latest" "GET" "$SENSOR_URL/api/v1/public/water-levels/latest" "-H 'X-API-Key: test-key-123'"
test_api "Moisture Latest" "GET" "$SENSOR_URL/api/v1/public/moisture/latest" "-H 'X-API-Key: test-key-123'"
test_api "AOS Latest" "GET" "$SENSOR_URL/api/v1/public/aos/latest" "-H 'X-API-Key: test-key-123'"
test_api "Water Level Timeseries" "GET" "$SENSOR_URL/api/v1/public/water-levels/timeseries" "-H 'X-API-Key: test-key-123'" "date=26/12/2568"

# Test RID-MS APIs
echo "=== RID-MS APIs ==="
test_api "List Shapefiles" "GET" "$RID_URL/api/v1/rid-ms/shapefiles" "-H 'X-API-Key: test-key-123'"
test_api "Zone 1 Parcels" "GET" "$RID_URL/api/v1/rid-ms/zones/Zone1/parcels" "-H 'X-API-Key: test-key-123'"

echo "✅ API testing complete"
EOF

    chmod +x test-all-endpoints.sh
}

# Main execution
main() {
    echo ""
    
    # Check prerequisites
    check_cloudflared
    
    # Check if services are already running
    if lsof -i:3001 &> /dev/null; then
        echo -e "${RED}❌ Port 3001 is already in use${NC}"
        echo "Please stop the existing service first"
        exit 1
    fi
    
    if lsof -i:3002 &> /dev/null; then
        echo -e "${RED}❌ Port 3002 is already in use${NC}"
        echo "Please stop the existing service first"
        exit 1
    fi
    
    # Start services
    start_sensor_data
    start_rid_ms
    
    # Start tunnels
    start_tunnels
    
    # Create documentation
    create_test_docs
    create_api_tests
    
    echo ""
    echo "========================================="
    echo -e "${GREEN}🎉 Test Environment Ready!${NC}"
    echo "========================================="
    echo ""
    echo "📄 Test URLs and examples: test-environment-info.txt"
    echo "🧪 Run tests: ./test-all-endpoints.sh"
    echo "⏹️  Stop services: ./stop-test-environment.sh"
    echo ""
    echo "🌐 Public URLs:"
    echo "   Sensor API: $SENSOR_URL"
    echo "   RID-MS API: $RID_URL"
    echo ""
    echo "These URLs are publicly accessible for testing!"
}

# Run main
main