#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting GIS Services in Background...${NC}"
echo "======================================"

# Function to check if process is already running
check_process() {
    if pgrep -f "$1" > /dev/null; then
        echo -e "${YELLOW}⚠️  $2 is already running${NC}"
        return 1
    fi
    return 0
}

# Create logs directory
mkdir -p logs

# 1. Start GIS API Service
if check_process "gis.*src/index.ts" "GIS API Service"; then
    echo -e "${GREEN}Starting GIS API Service...${NC}"
    nohup npm run dev > logs/gis-api.log 2>&1 &
    GIS_PID=$!
    echo $GIS_PID > .gis-api.pid
    echo -e "${GREEN}✓${NC} GIS API started (PID: $GIS_PID)"
    echo "   Log: logs/gis-api.log"
else
    GIS_PID=$(pgrep -f "gis.*src/index.ts")
    echo "   PID: $GIS_PID"
fi

# 2. Start GIS Queue Processor
if check_process "shapefile-queue-processor" "GIS Queue Processor"; then
    echo -e "${GREEN}Starting GIS Queue Processor...${NC}"
    nohup npm run queue:processor > logs/gis-queue-processor.log 2>&1 &
    QUEUE_PID=$!
    echo $QUEUE_PID > .gis-queue.pid
    echo -e "${GREEN}✓${NC} Queue Processor started (PID: $QUEUE_PID)"
    echo "   Log: logs/gis-queue-processor.log"
else
    QUEUE_PID=$(pgrep -f "shapefile-queue-processor")
    echo "   PID: $QUEUE_PID"
fi

# Wait a moment for services to start
sleep 3

# Check status
echo -e "\n${YELLOW}Service Status:${NC}"
echo "==============="

# Check if GIS API is responding
if curl -s http://localhost:3007/health > /dev/null; then
    echo -e "${GREEN}✓${NC} GIS API: http://localhost:3007 (healthy)"
else
    echo -e "${RED}✗${NC} GIS API: Not responding yet (check logs/gis-api.log)"
fi

# Check queue processor
if ps -p ${QUEUE_PID:-0} > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Queue Processor: Running"
else
    echo -e "${RED}✗${NC} Queue Processor: Not running (check logs/gis-queue-processor.log)"
fi

echo -e "\n${YELLOW}Commands:${NC}"
echo "========="
echo "View logs:"
echo "  tail -f logs/gis-api.log"
echo "  tail -f logs/gis-queue-processor.log"
echo ""
echo "Stop services:"
echo "  ./stop-gis-background.sh"
echo ""
echo "Check status:"
echo "  ./status-gis.sh"