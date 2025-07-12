#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Stopping GIS Services...${NC}"
echo "========================"

# Function to stop process
stop_process() {
    local PID_FILE=$1
    local SERVICE_NAME=$2
    
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            kill $PID
            echo -e "${GREEN}✓${NC} Stopped $SERVICE_NAME (PID: $PID)"
            rm "$PID_FILE"
        else
            echo -e "${YELLOW}⚠️  $SERVICE_NAME was not running (stale PID file)${NC}"
            rm "$PID_FILE"
        fi
    else
        # Try to find process by pattern
        if [ "$SERVICE_NAME" = "GIS API" ]; then
            PIDS=$(pgrep -f "gis.*src/index.ts")
        else
            PIDS=$(pgrep -f "shapefile-queue-processor")
        fi
        
        if [ -n "$PIDS" ]; then
            for PID in $PIDS; do
                kill $PID
                echo -e "${GREEN}✓${NC} Stopped $SERVICE_NAME (PID: $PID)"
            done
        else
            echo -e "${YELLOW}⚠️  $SERVICE_NAME is not running${NC}"
        fi
    fi
}

# Stop services
stop_process ".gis-api.pid" "GIS API"
stop_process ".gis-queue.pid" "GIS Queue Processor"

# Also kill any orphaned processes
pkill -f "gis.*npm run dev" 2>/dev/null
pkill -f "gis.*queue:processor" 2>/dev/null

echo -e "\n${GREEN}Done!${NC} All GIS services stopped."