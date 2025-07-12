#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================"
echo -e "Stopping Munbon Microservices"
echo -e "======================================${NC}"

# Function to stop process
stop_process() {
    local pid_file=$1
    local service_name=$2
    
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        if ps -p $PID > /dev/null 2>&1; then
            kill $PID
            echo -e "${GREEN}✓ Stopped $service_name (PID: $PID)${NC}"
            rm "$pid_file"
        else
            echo -e "${YELLOW}⚠️  $service_name was not running${NC}"
            rm "$pid_file"
        fi
    else
        echo -e "${YELLOW}⚠️  No PID file for $service_name${NC}"
    fi
}

# Stop all services
echo -e "\n${YELLOW}Stopping services...${NC}"

# Stop GIS services
stop_process ".gis-api.pid" "GIS API Service"
stop_process ".gis-queue.pid" "GIS Queue Processor"

# Stop Sensor Data services
stop_process ".sensor-api.pid" "Sensor Data API"
stop_process ".sensor-consumer.pid" "Sensor Data Consumer"

# Also kill any remaining processes
echo -e "\n${YELLOW}Cleaning up any remaining processes...${NC}"

# Kill GIS processes
pkill -f "gis.*src/index.ts" 2>/dev/null && echo -e "${GREEN}✓ Killed remaining GIS processes${NC}"
pkill -f "shapefile-queue-processor" 2>/dev/null && echo -e "${GREEN}✓ Killed remaining queue processors${NC}"

# Kill Sensor Data processes
pkill -f "sensor-data.*src/index.js" 2>/dev/null && echo -e "${GREEN}✓ Killed remaining sensor processes${NC}"
pkill -f "consumer/main.js" 2>/dev/null && echo -e "${GREEN}✓ Killed remaining consumers${NC}"

echo -e "\n${GREEN}All services stopped!${NC}"

# Check if any services are still running
echo -e "\n${BLUE}Checking remaining services...${NC}"

if lsof -Pi :3007 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}✗ Port 3007 is still in use${NC}"
else
    echo -e "${GREEN}✓ Port 3007 is free${NC}"
fi

if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}✗ Port 3000 is still in use${NC}"
else
    echo -e "${GREEN}✓ Port 3000 is free${NC}"
fi