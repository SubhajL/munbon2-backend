#!/bin/bash
# Script to start BFF Water Planning service with mock server

echo "Starting Water Planning BFF with Mock Server..."
echo "=============================================="

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if mock server directory exists
if [ ! -d "../mock-server" ]; then
    echo -e "${RED}Error: Mock server directory not found!${NC}"
    echo "Expected location: ../mock-server"
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    # Kill mock server
    if [ ! -z "$MOCK_PID" ]; then
        kill $MOCK_PID 2>/dev/null
        echo "Mock server stopped"
    fi
    # Kill BFF service
    if [ ! -z "$BFF_PID" ]; then
        kill $BFF_PID 2>/dev/null
        echo "BFF service stopped"
    fi
    exit 0
}

# Set trap for cleanup
trap cleanup INT TERM

# Start mock server
echo -e "${GREEN}Starting Mock Server on port 3099...${NC}"
cd ../mock-server
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi
python src/main.py &
MOCK_PID=$!
cd - > /dev/null

# Wait for mock server to start
echo "Waiting for mock server to start..."
sleep 3

# Check if mock server is running
if ! curl -s http://localhost:3099/health > /dev/null; then
    echo -e "${RED}Mock server failed to start!${NC}"
    cleanup
    exit 1
fi
echo -e "${GREEN}✓ Mock server is running${NC}"

# Start BFF service
echo -e "\n${GREEN}Starting BFF Water Planning service on port 3022...${NC}"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Ensure USE_MOCK_SERVER is set
export USE_MOCK_SERVER=true
export MOCK_SERVER_URL=http://localhost:3099

# Start the BFF service
python src/main.py &
BFF_PID=$!

# Wait for BFF to start
echo "Waiting for BFF service to start..."
sleep 5

# Check if BFF is running
if ! curl -s http://localhost:3022/health > /dev/null 2>&1; then
    echo -e "${YELLOW}Note: BFF health endpoint may not be available, checking GraphQL...${NC}"
fi

echo -e "\n${GREEN}Services are running!${NC}"
echo "=============================================="
echo "Mock Server: http://localhost:3099"
echo "Mock Server Docs: http://localhost:3099/docs"
echo "BFF Service: http://localhost:3022"
echo "GraphQL Playground: http://localhost:3022/graphql"
echo ""
echo "Press Ctrl+C to stop all services"
echo "=============================================="

# Wait for interrupt
wait