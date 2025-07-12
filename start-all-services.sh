#!/bin/bash

echo "🚀 Starting Munbon Backend Services..."
echo "===================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        echo -e "${GREEN}✓${NC} Port $1 is active"
        return 0
    else
        echo -e "${RED}✗${NC} Port $1 is not active"
        return 1
    fi
}

echo -e "\n${YELLOW}1. Checking Databases...${NC}"
check_port 5434 || echo "   Start PostgreSQL: docker-compose up -d postgres"
check_port 27017 || echo "   Start MongoDB: brew services start mongodb-community"
check_port 6379 || echo "   Start Redis: brew services start redis"
check_port 8086 || echo "   Start InfluxDB: brew services start influxdb"

echo -e "\n${YELLOW}2. Starting Microservices...${NC}"

# Start services using tmux sessions
if command -v tmux &> /dev/null; then
    echo "Starting services in tmux sessions..."
    
    # Create new tmux session
    tmux new-session -d -s munbon
    
    # Auth Service
    tmux new-window -t munbon:1 -n 'auth'
    tmux send-keys -t munbon:1 'cd services/auth && npm run dev' C-m
    
    # Sensor Data Service
    tmux new-window -t munbon:2 -n 'sensor-api'
    tmux send-keys -t munbon:2 'cd services/sensor-data && npm run dev' C-m
    
    # Sensor Consumer
    tmux new-window -t munbon:3 -n 'sensor-consumer'
    tmux send-keys -t munbon:3 'cd services/sensor-data && npm run consumer' C-m
    
    # GIS Service
    tmux new-window -t munbon:4 -n 'gis-api'
    tmux send-keys -t munbon:4 'cd services/gis && npm run dev' C-m
    
    # GIS Queue Processor
    tmux new-window -t munbon:5 -n 'gis-queue'
    tmux send-keys -t munbon:5 'cd services/gis && npm run queue:processor' C-m
    
    # ROS Service
    tmux new-window -t munbon:6 -n 'ros'
    tmux send-keys -t munbon:6 'cd services/ros && npm run dev' C-m
    
    echo -e "${GREEN}✓${NC} Services started in tmux session 'munbon'"
    echo "   Use 'tmux attach -t munbon' to view"
    echo "   Use 'tmux kill-session -t munbon' to stop all"
    
else
    echo -e "${RED}tmux not found. Install with: brew install tmux${NC}"
    echo "Alternative: Use PM2 for process management"
fi

echo -e "\n${YELLOW}3. Service Status:${NC}"
sleep 3
echo "Auth Service:        http://localhost:3001"
check_port 3001
echo "Sensor Data API:     http://localhost:3003"
check_port 3003
echo "GIS Service:         http://localhost:3007"
check_port 3007
echo "ROS Service:         http://localhost:3047"
check_port 3047

echo -e "\n${YELLOW}4. AWS Lambda Endpoints:${NC}"
echo "Sensor Ingestion: https://c0zc2kfzd6.execute-api.ap-southeast-1.amazonaws.com/dev"
echo "GIS Upload:       https://6wls4auo90.execute-api.ap-southeast-1.amazonaws.com/dev"

echo -e "\n${GREEN}Done!${NC} Check service logs in tmux windows."