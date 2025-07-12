#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}GIS Services Status${NC}"
echo "==================="
echo ""

# Check GIS API
echo -e "${YELLOW}1. GIS API Service:${NC}"
if pgrep -f "gis.*src/index.ts" > /dev/null; then
    PID=$(pgrep -f "gis.*src/index.ts")
    echo -e "   ${GREEN}✓ Running${NC} (PID: $PID)"
    
    # Check HTTP endpoint
    if curl -s http://localhost:3007/health > /dev/null 2>&1; then
        HEALTH=$(curl -s http://localhost:3007/health | jq -r '.status' 2>/dev/null || echo "unknown")
        echo -e "   ${GREEN}✓ Healthy${NC} (http://localhost:3007)"
        echo "     Status: $HEALTH"
    else
        echo -e "   ${RED}✗ Not responding${NC} on port 3007"
    fi
else
    echo -e "   ${RED}✗ Not running${NC}"
fi

# Check Queue Processor
echo -e "\n${YELLOW}2. GIS Queue Processor:${NC}"
if pgrep -f "shapefile-queue-processor" > /dev/null; then
    PID=$(pgrep -f "shapefile-queue-processor")
    echo -e "   ${GREEN}✓ Running${NC} (PID: $PID)"
else
    echo -e "   ${RED}✗ Not running${NC}"
fi

# Check logs
echo -e "\n${YELLOW}3. Recent Logs:${NC}"
if [ -f "logs/gis-api.log" ]; then
    echo "   GIS API (last 5 lines):"
    tail -5 logs/gis-api.log | sed 's/^/     /'
fi

if [ -f "logs/gis-queue-processor.log" ]; then
    echo -e "\n   Queue Processor (last 5 lines):"
    tail -5 logs/gis-queue-processor.log | sed 's/^/     /'
fi

# Check SQS Queue
echo -e "\n${YELLOW}4. Queue Status:${NC}"
if command -v aws &> /dev/null; then
    QUEUE_URL="https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-queue"
    MESSAGES=$(aws sqs get-queue-attributes \
        --queue-url "$QUEUE_URL" \
        --attribute-names ApproximateNumberOfMessages \
        --region ap-southeast-1 \
        --query 'Attributes.ApproximateNumberOfMessages' \
        --output text 2>/dev/null || echo "unknown")
    echo "   Messages in queue: $MESSAGES"
else
    echo "   AWS CLI not available"
fi

# Check database connection
echo -e "\n${YELLOW}5. Database Connection:${NC}"
if psql -U postgres -h localhost -d munbon_gis -c "SELECT 1;" &> /dev/null; then
    echo -e "   ${GREEN}✓ Connected${NC} to munbon_gis"
    
    # Check recent uploads
    UPLOADS=$(psql -U postgres -h localhost -d munbon_gis -t -c \
        "SELECT COUNT(*) FROM shape_file_uploads WHERE created_at > NOW() - INTERVAL '24 hours';" 2>/dev/null | xargs)
    echo "   Uploads in last 24h: ${UPLOADS:-0}"
else
    echo -e "   ${RED}✗ Cannot connect${NC} to munbon_gis database"
fi

echo -e "\n${YELLOW}6. Quick Commands:${NC}"
echo "   Start services:  ./start-gis-background.sh"
echo "   Stop services:   ./stop-gis-background.sh"
echo "   View API logs:   tail -f logs/gis-api.log"
echo "   View queue logs: tail -f logs/gis-queue-processor.log"