#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================"
echo -e "Starting Munbon Services with PM2"
echo -e "======================================${NC}"

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

# 1. Check prerequisites
echo -e "\n${YELLOW}1. Checking Docker services...${NC}"

# Start databases if not running
docker-compose up -d postgres timescaledb redis mongodb influxdb

# Wait for databases to be ready
echo -e "\n${YELLOW}Waiting for databases to initialize...${NC}"
sleep 5

# Check databases
if ! check_port 5434; then
    echo -e "${RED}✗ PostgreSQL (PostGIS) is not running on port 5434${NC}"
    exit 1
fi

if ! check_port 5433; then
    echo -e "${RED}✗ TimescaleDB is not running on port 5433${NC}"
    exit 1
fi

if ! check_port 6379; then
    echo -e "${RED}✗ Redis is not running on port 6379${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All databases are running${NC}"

# 2. Start PM2 services
echo -e "\n${YELLOW}2. Starting PM2 services...${NC}"

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo -e "${RED}PM2 is not installed. Install with: npm install -g pm2${NC}"
    exit 1
fi

# Delete any existing PM2 processes
pm2 delete all 2>/dev/null || true

# Start PM2 ecosystem
pm2 start pm2-ecosystem.config.js

# 3. Start additional services not in PM2
echo -e "\n${YELLOW}3. Starting additional services...${NC}"

# GIS Service (if not already in PM2)
if ! pm2 list | grep -q "gis-api"; then
    cd services/gis
    pm2 start npm --name "gis-api" -- run dev
    pm2 start npm --name "gis-queue" -- run queue:processor
    cd ../..
fi

# Wait for services to start
echo -e "\n${YELLOW}Waiting for services to initialize...${NC}"
sleep 5

# 4. Service Status
echo -e "\n${BLUE}Service Status:${NC}"
echo "====================="
pm2 status

# 5. Health Checks
echo -e "\n${BLUE}Health Checks:${NC}"
echo "================"

# Check Unified API/Sensor API on port 3000
if curl -s http://localhost:3000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Unified API (Sensor Data)${NC}: http://localhost:3000"
else
    echo -e "${YELLOW}⚠ Unified API not responding yet${NC}"
fi

# Check GIS Service
if curl -s http://localhost:3007/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ GIS Service${NC}: http://localhost:3007"
else
    echo -e "${YELLOW}⚠ GIS Service not responding yet${NC}"
fi

# 6. Display endpoints
echo -e "\n${BLUE}API Endpoints:${NC}"
echo "=============="
echo -e "${YELLOW}Unified API (Port 3000):${NC}"
echo "  - Water Level: POST http://localhost:3000/api/v1/telemetry/water-level"
echo "  - Moisture: POST http://localhost:3000/api/v1/telemetry/moisture"
echo "  - External API: GET http://localhost:3000/api/v1/external/*"
echo ""
echo -e "${YELLOW}Cloudflare Tunnel:${NC}"
echo "  - Check logs: pm2 logs quick-tunnel"
echo ""
echo -e "${YELLOW}GIS Service (Port 3007):${NC}"
echo "  - Upload: POST http://localhost:3007/api/v1/gis/shapefiles/upload"
echo "  - Parcels: GET http://localhost:3007/api/v1/gis/parcels"

# 7. Logs and monitoring
echo -e "\n${BLUE}Monitoring:${NC}"
echo "==========="
echo "  - View all logs: pm2 logs"
echo "  - View specific: pm2 logs sensor-api"
echo "  - Monitor: pm2 monit"
echo "  - Status: pm2 status"

echo -e "\n${BLUE}To stop all services:${NC}"
echo "===================="
echo "  pm2 stop all"
echo "  pm2 delete all"
echo "  docker-compose down"

echo -e "\n${GREEN}All services started successfully!${NC}"