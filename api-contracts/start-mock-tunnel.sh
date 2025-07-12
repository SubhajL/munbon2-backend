#!/bin/bash

# Start Mock API Server with Cloudflare Tunnel
# This script starts both the mock server and tunnel in one process

set -e

echo "🚀 Starting Mock API Server with Cloudflare Tunnel"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo -e "${RED}Error: cloudflared is not installed${NC}"
    echo "Install with: brew install cloudflare/cloudflare/cloudflared"
    exit 1
fi

# Check if prism is available
if ! npx prism --version &> /dev/null; then
    echo -e "${YELLOW}Installing Prism CLI...${NC}"
    npm install -g @stoplight/prism-cli
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    if [ ! -z "$MOCK_PID" ]; then
        kill $MOCK_PID 2>/dev/null || true
    fi
    if [ ! -z "$TUNNEL_PID" ]; then
        kill $TUNNEL_PID 2>/dev/null || true
    fi
    exit 0
}

trap cleanup EXIT INT TERM

# Start mock server in background
echo -e "${BLUE}Starting mock API server on port 4010...${NC}"
npx prism mock openapi/sensor-data-service.yaml -p 4010 -h 0.0.0.0 &
MOCK_PID=$!

# Wait for mock server to start
sleep 3

# Check if mock server is running
if ! kill -0 $MOCK_PID 2>/dev/null; then
    echo -e "${RED}Failed to start mock server${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Mock server started${NC}"
echo ""

# Start Cloudflare tunnel
echo -e "${BLUE}Starting Cloudflare tunnel...${NC}"
TEMP_FILE=$(mktemp)

# Run tunnel and capture output
cloudflared tunnel --url http://localhost:4010 > $TEMP_FILE 2>&1 &
TUNNEL_PID=$!

# Wait for tunnel URL
echo -n "Waiting for tunnel URL"
for i in {1..30}; do
    if grep -q "trycloudflare.com" $TEMP_FILE 2>/dev/null; then
        echo ""
        break
    fi
    echo -n "."
    sleep 1
done

# Extract tunnel URL
TUNNEL_URL=$(grep -o 'https://[a-zA-Z0-9\-]*\.trycloudflare\.com' $TEMP_FILE | head -1)

if [ -n "$TUNNEL_URL" ]; then
    echo -e "${GREEN}✓ Tunnel established!${NC}"
    echo ""
    echo "=============================================="
    echo -e "${GREEN}Mock API Server is ready!${NC}"
    echo "=============================================="
    echo ""
    echo -e "${BLUE}Public URL:${NC} $TUNNEL_URL"
    echo -e "${BLUE}Local URL:${NC} http://localhost:4010"
    echo ""
    echo -e "${GREEN}Example Endpoints:${NC}"
    echo "• GET $TUNNEL_URL/api/v1/sensors"
    echo "• GET $TUNNEL_URL/api/v1/sensors/{id}"
    echo "• POST $TUNNEL_URL/api/v1/telemetry"
    echo "• GET $TUNNEL_URL/api/v1/telemetry/latest"
    echo ""
    echo -e "${GREEN}Test Commands:${NC}"
    echo "curl $TUNNEL_URL/api/v1/sensors"
    echo "curl -H 'Authorization: Bearer mock-token' $TUNNEL_URL/api/v1/sensors"
    echo ""
    echo -e "${YELLOW}Note: This is a temporary URL. Save it if needed.${NC}"
    echo "$TUNNEL_URL" > mock-tunnel-url.txt
    echo -e "${BLUE}URL saved to: mock-tunnel-url.txt${NC}"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop both services${NC}"
    echo ""
    
    # Keep running
    wait
else
    echo -e "${RED}Failed to get tunnel URL${NC}"
    cat $TEMP_FILE
    exit 1
fi