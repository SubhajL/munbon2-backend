#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================"
echo -e "Starting Munbon Microservices"
echo -e "======================================${NC}"

# Function to check if port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        echo -e "${YELLOW}⚠️  Port $1 is already in use${NC}"
        return 1
    fi
    return 0
}

# Create logs directory
mkdir -p logs

# 1. Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

# Check databases
if ! pg_isready -h localhost -p 5434 > /dev/null 2>&1; then
    echo -e "${RED}✗ PostgreSQL (PostGIS) is not running on port 5434${NC}"
    echo "  Run: docker-compose up -d postgres"
    exit 1
fi

if ! pg_isready -h localhost -p 5433 > /dev/null 2>&1; then
    echo -e "${RED}✗ TimescaleDB is not running on port 5433${NC}"
    echo "  Run: docker-compose up -d timescaledb"
    exit 1
fi

echo -e "${GREEN}✓ Databases are running${NC}"

# 2. Start GIS Service
echo -e "\n${YELLOW}Starting GIS Service...${NC}"
cd services/gis

if check_port 3007; then
    # Start GIS API
    nohup npm run dev > ../../logs/gis-api.log 2>&1 &
    GIS_API_PID=$!
    echo $GIS_API_PID > ../../.gis-api.pid
    echo -e "${GREEN}✓ GIS API started (PID: $GIS_API_PID)${NC}"
    
    # Start GIS Queue Processor
    nohup npm run queue:processor > ../../logs/gis-queue.log 2>&1 &
    GIS_QUEUE_PID=$!
    echo $GIS_QUEUE_PID > ../../.gis-queue.pid
    echo -e "${GREEN}✓ GIS Queue Processor started (PID: $GIS_QUEUE_PID)${NC}"
fi

cd ../..

# 3. Start Sensor Data Service
echo -e "\n${YELLOW}Starting Sensor Data Service...${NC}"
cd services/sensor-data

if check_port 3003; then
    # Set environment variables
    export PORT=3003
    export TIMESCALE_HOST=localhost
    export TIMESCALE_PORT=5433
    export TIMESCALE_DB=sensor_data
    export TIMESCALE_USER=postgres
    export TIMESCALE_PASSWORD=postgres
    export VALID_TOKENS="munbon-ridr-water-level:water-level,munbon-m2m-moisture:moisture"
    export EXTERNAL_API_KEYS="rid-ms-dev-1234567890abcdef,test-key-fedcba0987654321"
    
    # Start Sensor API (runs on port 3001 by default)
    nohup npm run dev > ../../logs/sensor-api.log 2>&1 &
    SENSOR_API_PID=$!
    echo $SENSOR_API_PID > ../../.sensor-api.pid
    echo -e "${GREEN}✓ Sensor Data API started (PID: $SENSOR_API_PID)${NC}"
    
    # Start SQS Consumer (background worker - no port)
    nohup npm run consumer > ../../logs/sensor-consumer.log 2>&1 &
    SENSOR_CONSUMER_PID=$!
    echo $SENSOR_CONSUMER_PID > ../../.sensor-consumer.pid
    echo -e "${GREEN}✓ Sensor Data Consumer started (PID: $SENSOR_CONSUMER_PID) - Background Worker${NC}"
fi

cd ../..

# Wait for services to start
echo -e "\n${YELLOW}Waiting for services to initialize...${NC}"
sleep 5

# 4. Health Check
echo -e "\n${BLUE}Service Health Check:${NC}"
echo "====================="

# Check GIS Service
if curl -s http://localhost:3007/health > /dev/null; then
    echo -e "${GREEN}✓ GIS Service${NC}: http://localhost:3007"
else
    echo -e "${RED}✗ GIS Service${NC}: Not responding"
fi

# Check Sensor Data Service
if curl -s http://localhost:3003/health > /dev/null; then
    echo -e "${GREEN}✓ Sensor Data Service${NC}: http://localhost:3003"
else
    echo -e "${RED}✗ Sensor Data Service${NC}: Not responding"
fi

# 5. Display API Endpoints
echo -e "\n${BLUE}API Endpoints:${NC}"
echo "=============="
echo -e "${YELLOW}GIS Service (Port 3007):${NC}"
echo "  - Upload Shape File: POST http://localhost:3007/api/v1/gis/shapefiles/upload"
echo "  - Get Parcels: GET http://localhost:3007/api/v1/gis/parcels"
echo "  - Get Zones: GET http://localhost:3007/api/v1/gis/zones"

echo -e "\n${YELLOW}Sensor Data Service (Port 3003):${NC}"
echo "  - Ingest Water Level: POST http://localhost:3003/api/v1/telemetry/water-level"
echo "  - Ingest Moisture: POST http://localhost:3003/api/v1/telemetry/moisture"
echo "  - Query Data: GET http://localhost:3003/api/v1/external/water-level"

# 6. Display Logs
echo -e "\n${BLUE}Log Files:${NC}"
echo "=========="
echo "  - GIS API: tail -f logs/gis-api.log"
echo "  - GIS Queue: tail -f logs/gis-queue.log"
echo "  - Sensor API: tail -f logs/sensor-api.log"
echo "  - Sensor Consumer: tail -f logs/sensor-consumer.log"

# 7. Stop command
echo -e "\n${BLUE}To stop all services:${NC}"
echo "===================="
echo "  ./stop-all-microservices.sh"

echo -e "\n${GREEN}All services started successfully!${NC}"