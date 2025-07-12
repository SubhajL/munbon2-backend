#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================"
echo -e "PM2 Service Status Dashboard"
echo -e "======================================${NC}"

# Function to check if port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Active"
        return 0
    else
        echo -e "${RED}✗${NC} Not listening"
        return 1
    fi
}

# Check PM2 status
if ! command -v pm2 &> /dev/null; then
    echo -e "${RED}PM2 is not installed${NC}"
    exit 1
fi

echo -e "\n${YELLOW}PM2 Process Status:${NC}"
pm2 status

echo -e "\n${YELLOW}Service Health Checks:${NC}"
echo "========================"

# API Services
echo -e "\n${BLUE}API Services:${NC}"
echo -n "• Unified API (3000):        "
check_port 3000
echo -n "• Auth Service (3001):       "
check_port 3001
echo -n "• Sensor Data API (3003):    "
check_port 3003
echo -n "• GIS Service (3007):        "
check_port 3007

# Databases
echo -e "\n${BLUE}Databases:${NC}"
echo -n "• PostgreSQL/PostGIS (5434): "
check_port 5434
echo -n "• TimescaleDB (5433):        "
check_port 5433
echo -n "• Redis (6379):              "
check_port 6379
echo -n "• MongoDB (27017):           "
check_port 27017

# Check Cloudflare tunnel
echo -e "\n${BLUE}Cloudflare Tunnel:${NC}"
TUNNEL_URL=$(pm2 logs cloudflare-tunnel --lines 50 --nostream 2>/dev/null | grep -oE "https://[a-z-]+\.trycloudflare\.com" | tail -1)
if [ -n "$TUNNEL_URL" ]; then
    echo -e "• Current URL: ${GREEN}$TUNNEL_URL${NC}"
else
    echo -e "• Status: ${YELLOW}No tunnel URL found${NC}"
fi

# Memory usage
echo -e "\n${BLUE}Memory Usage:${NC}"
pm2 list | grep -E "unified-api|sensor-data-service|gis-api" | while read line; do
    name=$(echo $line | awk '{print $2}')
    mem=$(echo $line | awk '{print $11}')
    echo "• $name: $mem"
done

# Logs
echo -e "\n${BLUE}Recent Errors (last 5 lines):${NC}"
echo "=============================="
for service in unified-api sensor-data-service sensor-consumer gis-api gis-queue-processor; do
    if pm2 describe $service &>/dev/null; then
        echo -e "\n${YELLOW}$service:${NC}"
        pm2 logs $service --err --lines 5 --nostream 2>/dev/null | tail -5
    fi
done

echo -e "\n${BLUE}Quick Commands:${NC}"
echo "=============="
echo "• View all logs:        pm2 logs"
echo "• View specific logs:   pm2 logs <service-name>"
echo "• Restart all:          pm2 restart all"
echo "• Stop all:             pm2 stop all"
echo "• Monitor:              pm2 monit"
echo "• Save configuration:   pm2 save"
echo "• Startup on boot:      pm2 startup"