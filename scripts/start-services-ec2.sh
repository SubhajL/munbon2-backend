#!/bin/bash

# Start all services for EC2 testing
# Uses EC2 consolidated PostgreSQL database

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Starting services for EC2 testing${NC}"
echo "=================================="

# EC2 Database Configuration
export POSTGRES_HOST="${EC2_HOST:-43.208.201.191}"
export POSTGRES_PORT="5432"
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="P@ssw0rd123!"
export TIMESCALE_HOST="${EC2_HOST:-43.208.201.191}"
export TIMESCALE_PORT="5432"  # Same as PostgreSQL
export TIMESCALE_PASSWORD="P@ssw0rd123!"

# Stop existing services first
echo -e "\n${YELLOW}Stopping existing services...${NC}"
pm2 stop all 2>/dev/null || true

# Start services with EC2 configuration
echo -e "\n${BLUE}Starting core services...${NC}"

# 1. Auth Service (3001)
echo "Starting Auth Service..."
cd /Users/subhajlimanond/dev/munbon2-backend/services/auth
PORT=3001 \
DATABASE_URL="postgresql://postgres:P@ssw0rd123!@${EC2_HOST:-43.208.201.191}:5432/munbon_dev?schema=auth" \
REDIS_URL="redis://localhost:6379" \
JWT_SECRET="local-dev-secret" \
npm run dev > /tmp/auth-service.log 2>&1 &
echo -e "${GREEN}✓ Auth Service started on port 3001${NC}"

# 2. GIS Service (3007)
echo "Starting GIS Service..."
cd /Users/subhajlimanond/dev/munbon2-backend/services/gis
PORT=3007 \
POSTGRES_HOST="${EC2_HOST:-43.208.201.191}" \
POSTGRES_PORT="5432" \
POSTGRES_DB="munbon_dev" \
POSTGRES_USER="postgres" \
POSTGRES_PASSWORD="P@ssw0rd123!" \
npm run dev > /tmp/gis-service.log 2>&1 &
echo -e "${GREEN}✓ GIS Service started on port 3007${NC}"

# 3. ROS Service (3047)
echo "Starting ROS Service..."
cd /Users/subhajlimanond/dev/munbon2-backend/services/ros
PORT=3047 \
DB_HOST="${EC2_HOST:-43.208.201.191}" \
DB_PORT="5432" \
DB_NAME="munbon_dev" \
DB_SCHEMA="ros" \
DB_USER="postgres" \
DB_PASSWORD="P@ssw0rd123!" \
npm run dev > /tmp/ros-service.log 2>&1 &
echo -e "${GREEN}✓ ROS Service started on port 3047${NC}"

# 4. Flow Monitoring Service (3011)
echo "Starting Flow Monitoring Service..."
cd /Users/subhajlimanond/dev/munbon2-backend/services/flow-monitoring
PORT=3011 \
DATABASE_URL="postgresql://postgres:P@ssw0rd123!@${EC2_HOST:-43.208.201.191}:5432/munbon_dev" \
REDIS_URL="redis://localhost:6379" \
python -m uvicorn src.main:app --host 0.0.0.0 --port 3011 > /tmp/flow-monitoring.log 2>&1 &
echo -e "${GREEN}✓ Flow Monitoring Service started on port 3011${NC}"

# 5. Weather Monitoring (3006)
echo "Starting Weather Monitoring Service..."
cd /Users/subhajlimanond/dev/munbon2-backend/services/weather-monitoring
PORT=3006 \
DATABASE_URL="postgresql://postgres:P@ssw0rd123!@${EC2_HOST:-43.208.201.191}:5432/sensor_data" \
TIMESCALE_HOST="${EC2_HOST:-43.208.201.191}" \
TIMESCALE_PORT="5432" \
TIMESCALE_DB="sensor_data" \
TIMESCALE_USER="postgres" \
TIMESCALE_PASSWORD="P@ssw0rd123!" \
npm run dev > /tmp/weather-monitoring.log 2>&1 &
echo -e "${GREEN}✓ Weather Monitoring Service started on port 3006${NC}"

# 6. Water Level Monitoring (3008)
echo "Starting Water Level Monitoring Service..."
cd /Users/subhajlimanond/dev/munbon2-backend/services/water-level-monitoring
PORT=3008 \
TIMESCALE_URL="postgresql://postgres:P@ssw0rd123!@${EC2_HOST:-43.208.201.191}:5432/sensor_data" \
npm run dev > /tmp/water-level-monitoring.log 2>&1 &
echo -e "${GREEN}✓ Water Level Monitoring Service started on port 3008${NC}"

# 7. AWD Control Service (3010)
echo "Starting AWD Control Service..."
cd /Users/subhajlimanond/dev/munbon2-backend/services/awd-control
PORT=3010 \
POSTGRES_HOST="${EC2_HOST:-43.208.201.191}" \
POSTGRES_PORT="5432" \
POSTGRES_DB="munbon_dev" \
POSTGRES_SCHEMA="awd" \
POSTGRES_USER="postgres" \
POSTGRES_PASSWORD="P@ssw0rd123!" \
TIMESCALE_HOST="${EC2_HOST:-43.208.201.191}" \
TIMESCALE_PORT="5432" \
TIMESCALE_DB="sensor_data" \
TIMESCALE_USER="postgres" \
TIMESCALE_PASSWORD="P@ssw0rd123!" \
npm run dev > /tmp/awd-control.log 2>&1 &
echo -e "${GREEN}✓ AWD Control Service started on port 3010${NC}"

# 8. Unified API Gateway (3000)
echo "Starting Unified API Gateway..."
cd /Users/subhajlimanond/dev/munbon2-backend/services/sensor-data
PORT=3000 \
POSTGRES_HOST="${EC2_HOST:-43.208.201.191}" \
POSTGRES_PORT="5432" \
POSTGRES_DB="munbon_dev" \
POSTGRES_USER="postgres" \
POSTGRES_PASSWORD="P@ssw0rd123!" \
TIMESCALE_HOST="${EC2_HOST:-43.208.201.191}" \
TIMESCALE_PORT="5432" \
TIMESCALE_DB="sensor_data" \
TIMESCALE_USER="postgres" \
TIMESCALE_PASSWORD="P@ssw0rd123!" \
node src/unified-api.js > /tmp/unified-api.log 2>&1 &
echo -e "${GREEN}✓ Unified API started on port 3000${NC}"

# Wait for services to start
echo -e "\n${YELLOW}Waiting for services to initialize...${NC}"
sleep 10

# Check service health
echo -e "\n${BLUE}Checking service health...${NC}"
for port in 3000 3001 3003 3006 3007 3008 3010 3011 3047; do
    if curl -s -f "http://localhost:$port/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Service on port $port is healthy${NC}"
    else
        echo -e "${RED}✗ Service on port $port is not responding${NC}"
    fi
done

echo -e "\n${BLUE}Services started! Check logs in /tmp/ for details${NC}"
echo "To stop all services: pkill -f 'node|python'"