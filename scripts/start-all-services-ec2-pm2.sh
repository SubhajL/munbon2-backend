#!/bin/bash

# Start all backend services using PM2 with EC2 database
# Alternative to Docker when builds are failing

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Starting All Backend Services with PM2 (EC2 Database)${NC}"
echo "======================================================="

# EC2 Database Configuration
export POSTGRES_HOST="${EC2_HOST:-43.208.201.191}"
export POSTGRES_PORT="5432"
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="P@ssw0rd123!"
export POSTGRES_DB="munbon_dev"
export TIMESCALE_HOST="${EC2_HOST:-43.208.201.191}"
export TIMESCALE_PORT="5432"
export TIMESCALE_USER="postgres"
export TIMESCALE_PASSWORD="P@ssw0rd123!"
export TIMESCALE_DB="sensor_data"
export JWT_SECRET="test-secret"
export REDIS_URL="redis://localhost:6379"

# Check EC2 connectivity
echo -e "\n${BLUE}Testing EC2 database connectivity...${NC}"
if PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d postgres -c "SELECT version();" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ EC2 database connection successful${NC}"
else
    echo -e "${RED}✗ Cannot connect to EC2 database${NC}"
    exit 1
fi

# Stop existing PM2 processes
echo -e "\n${BLUE}Stopping existing PM2 processes...${NC}"
pm2 delete all 2>/dev/null || true

# Kill processes on required ports
echo -e "\n${BLUE}Freeing up ports...${NC}"
PORTS="3000 3001 3003 3004 3006 3007 3008 3009 3010 3011 3012 3013 3014 3015 3016 3017 3047"
for port in $PORTS; do
    lsof -ti:$port | xargs kill -9 2>/dev/null || true
done

# Start Redis
echo -e "\n${BLUE}Starting Redis...${NC}"
redis-server --daemonize yes

# Function to start Node.js service
start_node_service() {
    local name=$1
    local path=$2
    local port=$3
    local extra_env=$4
    
    echo -e "\n${BLUE}Starting $name on port $port...${NC}"
    cd "$path"
    
    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo "Installing dependencies..."
        npm install
    fi
    
    # Start with PM2
    eval "PORT=$port $extra_env pm2 start npm --name \"$name\" -- run dev"
}

# Function to start Python service
start_python_service() {
    local name=$1
    local path=$2
    local port=$3
    local extra_env=$4
    
    echo -e "\n${BLUE}Starting $name on port $port...${NC}"
    cd "$path"
    
    # Create virtual environment if needed
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Install dependencies
    source venv/bin/activate
    pip install -r requirements.txt
    
    # Start with PM2
    eval "PORT=$port DATABASE_URL=\"postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB\" $extra_env pm2 start \"python -m uvicorn src.main:app --host 0.0.0.0 --port $port --reload\" --name \"$name\" --interpreter none"
}

# Start all services
cd /Users/subhajlimanond/dev/munbon2-backend

# 1. Auth Service (3001)
start_node_service "auth" "services/auth" "3001" "DATABASE_URL=\"postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB?schema=auth\""

# 2. Sensor Data Service (3003)
start_node_service "sensor-data" "services/sensor-data" "3003" "VALID_TOKENS=\"munbon-ridr-water-level:water-level,munbon-m2m-moisture:moisture\""

# 3. Sensor Data Consumer (3004)
cd services/sensor-data
PORT=3004 AWS_REGION=ap-southeast-1 AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY SQS_QUEUE_URL=$SQS_QUEUE_URL pm2 start npm --name "sensor-consumer" -- run consumer

# 4. Weather Monitoring (3006)
start_node_service "weather-monitoring" "services/weather-monitoring" "3006" "DATABASE_URL=\"postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$TIMESCALE_DB\""

# 5. GIS Service (3007)
start_node_service "gis" "services/gis" "3007" "GIS_SCHEMA=gis"

# 6. Water Level Monitoring (3008)
start_node_service "water-level-monitoring" "services/water-level-monitoring" "3008" "TIMESCALE_URL=\"postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$TIMESCALE_DB\""

# 7. Moisture Monitoring (3009)
start_node_service "moisture-monitoring" "services/moisture-monitoring" "3009" ""

# 8. AWD Control (3010)
start_node_service "awd-control" "services/awd-control" "3010" "POSTGRES_SCHEMA=awd"

# 9. Flow Monitoring (3011) - Python
start_python_service "flow-monitoring" "services/flow-monitoring" "3011" ""

# 10. RID Management (3012)
start_node_service "rid-ms" "services/rid-ms" "3012" "DATABASE_URL=\"postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB?schema=rid\""

# 11. ROS Service (3047)
start_node_service "ros" "services/ros" "3047" "DB_HOST=$POSTGRES_HOST DB_PORT=$POSTGRES_PORT DB_NAME=$POSTGRES_DB DB_SCHEMA=ros DB_USER=$POSTGRES_USER DB_PASSWORD=$POSTGRES_PASSWORD"

# 12. ROS-GIS Integration (3013) - Python
start_python_service "ros-gis-integration" "services/ros-gis-integration" "3013" "ROS_SERVICE_URL=http://localhost:3047 GIS_SERVICE_URL=http://localhost:3007"

# 13. Gravity Optimizer (3014) - Python
start_python_service "gravity-optimizer" "services/gravity-optimizer" "3014" ""

# 14. Water Accounting (3015) - Python
start_python_service "water-accounting" "services/water-accounting" "3015" ""

# 15. Sensor Network Management (3016)
start_node_service "sensor-network-management" "services/sensor-network-management" "3016" "DATABASE_URL=\"postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB?schema=sensor_network\""

# 16. Scheduler (3017) - Python
start_python_service "scheduler" "services/scheduler" "3017" ""

# 17. Unified API (3000)
cd services/sensor-data
PORT=3000 pm2 start node --name "unified-api" -- src/unified-api.js

# Wait for services to start
echo -e "\n${YELLOW}Waiting for services to initialize (30s)...${NC}"
sleep 30

# Show PM2 status
echo -e "\n${BLUE}Service Status:${NC}"
pm2 status

# Check health endpoints
echo -e "\n${BLUE}Checking service health...${NC}"
for port in $PORTS; do
    echo -ne "Port $port: "
    if curl -s -f "http://localhost:$port/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Healthy${NC}"
    elif curl -s -f "http://localhost:$port/" > /dev/null 2>&1; then
        echo -e "${YELLOW}✓ Running (no health endpoint)${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi
done

echo -e "\n${BLUE}All services started with PM2!${NC}"
echo "View logs: pm2 logs"
echo "Stop all: pm2 delete all"
echo "Save config: pm2 save"