#!/bin/bash

# Deploy all backend services using Docker Compose
# Uses production-ready configuration with EC2 database

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}===================================================${NC}"
echo -e "${BLUE}    Munbon Backend Services Deployment${NC}"
echo -e "${BLUE}    EC2 Database: 43.209.22.250:5432${NC}"
echo -e "${BLUE}===================================================${NC}"

# Function to check prerequisites
check_prerequisites() {
    echo -e "\n${BLUE}Checking prerequisites...${NC}"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}✗ Docker is not installed${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Docker is installed${NC}"
    
    # Check Docker daemon
    if ! docker info > /dev/null 2>&1; then
        echo -e "${YELLOW}Docker daemon is not running. Starting Colima...${NC}"
        colima start
        sleep 5
    fi
    echo -e "${GREEN}✓ Docker daemon is running${NC}"
    
    # Check EC2 connectivity
    echo -e "${BLUE}Testing EC2 database connectivity...${NC}"
    if PGPASSWORD=P@ssw0rd123! psql -h 43.209.22.250 -p 5432 -U postgres -d postgres -c "SELECT version();" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ EC2 database is accessible${NC}"
    else
        echo -e "${RED}✗ Cannot connect to EC2 database${NC}"
        echo "Please check your network connection and VPN if required"
        exit 1
    fi
}

# Function to prepare environment
prepare_environment() {
    echo -e "\n${BLUE}Preparing environment...${NC}"
    
    # Create .env file if not exists
    if [ ! -f .env ]; then
        echo -e "${YELLOW}Creating .env file...${NC}"
        cat > .env << 'EOF'
# AWS Configuration
AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
AWS_REGION=ap-southeast-1
SQS_QUEUE_URL=https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue

# JWT Configuration
JWT_SECRET=test-secret-for-development

# Sensor Tokens
VALID_TOKENS=munbon-ridr-water-level:water-level,munbon-m2m-moisture:moisture
EOF
        echo -e "${GREEN}✓ .env file created${NC}"
    else
        echo -e "${GREEN}✓ .env file exists${NC}"
    fi
}

# Function to clean up existing containers
cleanup_existing() {
    echo -e "\n${BLUE}Cleaning up existing containers...${NC}"
    
    # Stop and remove munbon containers
    docker-compose -f docker-compose.production.yml down 2>/dev/null || true
    docker rm -f $(docker ps -aq --filter "name=munbon-") 2>/dev/null || true
    
    echo -e "${GREEN}✓ Cleanup completed${NC}"
}

# Function to deploy services
deploy_services() {
    echo -e "\n${BLUE}Deploying services...${NC}"
    
    # Pull latest images
    echo -e "${YELLOW}Pulling Docker images...${NC}"
    docker-compose -f docker-compose.production.yml pull
    
    # Start services
    echo -e "${YELLOW}Starting services...${NC}"
    docker-compose -f docker-compose.production.yml up -d
    
    echo -e "${GREEN}✓ Services deployed${NC}"
}

# Function to wait for services
wait_for_services() {
    echo -e "\n${BLUE}Waiting for services to initialize...${NC}"
    
    # Wait for initial startup
    echo -ne "Initializing"
    for i in {1..30}; do
        echo -ne "."
        sleep 1
    done
    echo ""
}

# Function to check service health
check_services() {
    echo -e "\n${BLUE}Checking service health...${NC}"
    echo -e "${BLUE}===========================================${NC}"
    
    # Service list
    declare -a SERVICES=(
        "unified-api:3000:API Gateway"
        "auth:3001:Authentication"
        "sensor-data:3003:Sensor Data"
        "weather-monitoring:3006:Weather"
        "gis:3007:GIS"
        "water-level-monitoring:3008:Water Level"
        "moisture-monitoring:3009:Moisture"
        "awd-control:3010:AWD Control"
        "flow-monitoring:3011:Flow Monitor"
        "rid-ms:3012:RID Management"
        "ros-gis-integration:3013:ROS-GIS"
        "gravity-optimizer:3014:Gravity Opt"
        "water-accounting:3015:Water Account"
        "sensor-network-management:3016:Sensor Network"
        "scheduler:3017:Scheduler"
        "ros:3047:ROS"
    )
    
    HEALTHY=0
    UNHEALTHY=0
    
    for service_info in "${SERVICES[@]}"; do
        IFS=':' read -r container port name <<< "$service_info"
        
        # Check if container is running
        if docker ps | grep -q "munbon-$container"; then
            # Check health endpoint
            if curl -s -f "http://localhost:$port/health" > /dev/null 2>&1 || \
               curl -s -f "http://localhost:$port/api/health" > /dev/null 2>&1 || \
               curl -s -f "http://localhost:$port/" > /dev/null 2>&1; then
                echo -e "$name ($port): ${GREEN}✓ Running${NC}"
                ((HEALTHY++))
            else
                echo -e "$name ($port): ${YELLOW}⚠ Starting...${NC}"
                ((UNHEALTHY++))
            fi
        else
            echo -e "$name ($port): ${RED}✗ Not running${NC}"
            ((UNHEALTHY++))
        fi
    done
    
    # Check Redis
    if redis-cli ping > /dev/null 2>&1; then
        echo -e "Redis (6379): ${GREEN}✓ Running${NC}"
        ((HEALTHY++))
    else
        echo -e "Redis (6379): ${RED}✗ Not running${NC}"
        ((UNHEALTHY++))
    fi
    
    echo -e "${BLUE}===========================================${NC}"
    echo -e "Status: ${GREEN}$HEALTHY healthy${NC}, ${RED}$UNHEALTHY unhealthy${NC}"
}

# Function to show logs command
show_commands() {
    echo -e "\n${BLUE}Useful Commands:${NC}"
    echo "• View all logs:        docker-compose -f docker-compose.production.yml logs -f"
    echo "• View service logs:    docker-compose -f docker-compose.production.yml logs -f <service>"
    echo "• Stop all services:    docker-compose -f docker-compose.production.yml down"
    echo "• Restart service:      docker-compose -f docker-compose.production.yml restart <service>"
    echo "• Service status:       docker-compose -f docker-compose.production.yml ps"
    echo "• Container stats:      docker stats --no-stream"
}

# Function to handle failed containers
check_failed_containers() {
    FAILED=$(docker ps -a --filter "status=exited" --filter "name=munbon-" --format "{{.Names}}" | head -5)
    if [ ! -z "$FAILED" ]; then
        echo -e "\n${YELLOW}Some containers failed to start:${NC}"
        for container in $FAILED; do
            echo -e "${RED}• $container${NC}"
            echo "  Last error: $(docker logs $container 2>&1 | tail -1)"
        done
        echo -e "\n${YELLOW}Tip: Check logs with: docker logs <container-name>${NC}"
    fi
}

# Main execution
main() {
    echo -e "${BLUE}Starting deployment at $(date)${NC}\n"
    
    # Run deployment steps
    check_prerequisites
    prepare_environment
    cleanup_existing
    deploy_services
    wait_for_services
    check_services
    check_failed_containers
    show_commands
    
    echo -e "\n${BLUE}===================================================${NC}"
    echo -e "${GREEN}Deployment completed!${NC}"
    echo -e "${BLUE}===================================================${NC}"
}

# Run main function
main "$@"