#!/bin/bash

# Start all backend services using Docker Compose
# Connects to EC2 PostgreSQL database at ${EC2_HOST:-43.208.201.191}:5432

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Starting All Backend Services with Docker${NC}"
echo "=========================================="

# Check if .env file exists for AWS credentials
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found. Creating from template...${NC}"
    cat > .env << 'EOF'
# AWS Configuration
AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
SQS_QUEUE_URL=https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue
EOF
fi

# Function to check port availability
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${YELLOW}Port $port is in use. Attempting to free it...${NC}"
        # Get the PID using the port
        local pid=$(lsof -Pi :$port -sTCP:LISTEN -t 2>/dev/null)
        if [ ! -z "$pid" ]; then
            echo "Killing process $pid on port $port"
            kill -9 $pid 2>/dev/null || true
            sleep 1
        fi
    fi
}

# Check and free required ports
echo -e "\n${BLUE}Checking port availability...${NC}"
PORTS="3000 3001 3003 3006 3007 3008 3009 3010 3011 3012 3013 3014 3015 3016 3017 3047 6379"
for port in $PORTS; do
    check_port $port
done

# Stop any existing containers
echo -e "\n${BLUE}Stopping existing containers...${NC}"
docker-compose -f docker-compose.all-services.yml down 2>/dev/null || true

# Remove any orphaned containers
docker container prune -f 2>/dev/null || true

# Test EC2 database connectivity
echo -e "\n${BLUE}Testing EC2 database connectivity...${NC}"
if PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -p 5432 -U postgres -d postgres -c "SELECT version();" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ EC2 database connection successful${NC}"
else
    echo -e "${RED}✗ Cannot connect to EC2 database. Please check your connection.${NC}"
    exit 1
fi

# Start services
echo -e "\n${BLUE}Starting Docker services...${NC}"
docker-compose -f docker-compose.all-services.yml up -d

# Wait for services to initialize
echo -e "\n${YELLOW}Waiting for services to initialize (30s)...${NC}"
sleep 30

# Check service health
echo -e "\n${BLUE}Checking service health...${NC}"
echo "=========================================="

# Service list with names and ports
declare -a SERVICES=(
    "unified-api:3000"
    "auth:3001"
    "sensor-data:3003"
    "weather-monitoring:3006"
    "gis:3007"
    "water-level-monitoring:3008"
    "moisture-monitoring:3009"
    "awd-control:3010"
    "flow-monitoring:3011"
    "rid-ms:3012"
    "ros-gis-integration:3013"
    "gravity-optimizer:3014"
    "water-accounting:3015"
    "sensor-network-management:3016"
    "scheduler:3017"
    "ros:3047"
)

HEALTHY=0
UNHEALTHY=0

for service_info in "${SERVICES[@]}"; do
    IFS=':' read -r service port <<< "$service_info"
    
    # Check container status
    if docker ps | grep -q "munbon-$service"; then
        echo -ne "Checking $service (port $port)... "
        
        # Try health endpoint
        if curl -s -f "http://localhost:$port/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Healthy${NC}"
            ((HEALTHY++))
        elif curl -s -f "http://localhost:$port/api/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Healthy${NC}"
            ((HEALTHY++))
        elif curl -s -f "http://localhost:$port/" > /dev/null 2>&1; then
            echo -e "${YELLOW}✓ Running (no health endpoint)${NC}"
            ((HEALTHY++))
        else
            echo -e "${RED}✗ Not responding${NC}"
            ((UNHEALTHY++))
        fi
    else
        echo -e "$service (port $port)... ${RED}✗ Container not running${NC}"
        ((UNHEALTHY++))
    fi
done

# Redis check
echo -ne "Checking redis (port 6379)... "
if redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Healthy${NC}"
    ((HEALTHY++))
else
    echo -e "${RED}✗ Not responding${NC}"
    ((UNHEALTHY++))
fi

# Summary
echo -e "\n${BLUE}=========================================="
echo "Service Status Summary:"
echo -e "Healthy services: ${GREEN}$HEALTHY${NC}"
echo -e "Unhealthy services: ${RED}$UNHEALTHY${NC}"
echo -e "==========================================\n"

# Show container logs command
echo -e "${BLUE}Useful commands:${NC}"
echo "View all logs: docker-compose -f docker-compose.all-services.yml logs -f"
echo "View specific service logs: docker-compose -f docker-compose.all-services.yml logs -f <service-name>"
echo "Stop all services: docker-compose -f docker-compose.all-services.yml down"
echo "View container status: docker ps"

# Show any failed containers
FAILED_CONTAINERS=$(docker ps -a --filter "status=exited" --filter "name=munbon-" --format "table {{.Names}}\t{{.Status}}" | grep -v NAMES || true)
if [ ! -z "$FAILED_CONTAINERS" ]; then
    echo -e "\n${RED}Failed containers:${NC}"
    echo "$FAILED_CONTAINERS"
fi

exit 0