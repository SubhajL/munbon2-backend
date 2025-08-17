#!/bin/bash

# Debug Server Startup Script
# One-command launch for frontend integration debugging

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}     🔧 DEBUG SERVER - FRONTEND INTEGRATION${NC}"
echo -e "${BLUE}================================================${NC}"

# Function to check prerequisites
check_prerequisites() {
    echo -e "\n${YELLOW}Checking prerequisites...${NC}"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed${NC}"
        exit 1
    fi
    
    # Check Docker daemon
    if ! docker info > /dev/null 2>&1; then
        echo -e "${YELLOW}Starting Docker daemon...${NC}"
        if command -v colima &> /dev/null; then
            colima start
            sleep 5
        else
            echo -e "${RED}❌ Docker daemon is not running${NC}"
            exit 1
        fi
    fi
    
    # Check EC2 connectivity
    echo -e "${YELLOW}Testing EC2 database...${NC}"
    if PGPASSWORD=P@ssw0rd123! psql -h ${EC2_HOST:-43.208.201.191} -p 5432 -U postgres -d postgres -c "SELECT 1" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ EC2 database accessible${NC}"
    else
        echo -e "${RED}❌ Cannot connect to EC2 database${NC}"
        echo "Please check your network connection"
        exit 1
    fi
    
    echo -e "${GREEN}✅ All prerequisites met${NC}"
}

# Function to clean up old containers
cleanup() {
    echo -e "\n${YELLOW}Cleaning up old containers...${NC}"
    docker-compose -f docker-compose.debug.yml down 2>/dev/null || true
    docker rm -f $(docker ps -aq --filter "name=debug-") 2>/dev/null || true
    echo -e "${GREEN}✅ Cleanup complete${NC}"
}

# Function to start services
start_services() {
    echo -e "\n${BLUE}Starting debug services...${NC}"
    
    # Copy environment file
    cp .env.debug .env
    
    # Start services
    docker-compose -f docker-compose.debug.yml up -d
    
    echo -e "${GREEN}✅ Services starting...${NC}"
}

# Function to wait for services
wait_for_services() {
    echo -e "\n${YELLOW}Waiting for services to initialize...${NC}"
    
    # Wait for services to start
    sleep 10
    
    # Check health of critical services
    echo -ne "Checking services"
    for i in {1..20}; do
        echo -ne "."
        sleep 1
    done
    echo ""
}

# Function to show status
show_status() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${GREEN}✅ DEBUG SERVER READY${NC}"
    echo -e "${BLUE}================================================${NC}"
    
    echo -e "\n${BLUE}📍 Service URLs:${NC}"
    echo -e "  ${GREEN}API Gateway:${NC}     http://localhost:3000"
    echo -e "  ${GREEN}Auth Service:${NC}    http://localhost:3001"
    echo -e "  ${GREEN}Sensor Data:${NC}     http://localhost:3003"
    echo -e "  ${GREEN}GIS Service:${NC}     http://localhost:3007"
    echo -e "  ${GREEN}ROS Service:${NC}     http://localhost:3047"
    
    echo -e "\n${BLUE}🔧 Debug Tools:${NC}"
    echo -e "  ${GREEN}Debug Dashboard:${NC}  http://localhost:9999"
    echo -e "  ${GREEN}Request Viewer:${NC}   http://localhost:9998"
    
    echo -e "\n${BLUE}📚 API Documentation:${NC}"
    echo -e "  ${GREEN}Health Check:${NC}     GET http://localhost:3000/health"
    echo -e "  ${GREEN}Debug Info:${NC}       GET http://localhost:3000/debug/health"
    
    echo -e "\n${BLUE}🧪 Test Endpoints:${NC}"
    echo -e "  ${GREEN}Mock Login:${NC}       POST http://localhost:3001/auth/debug/login"
    echo -e "  ${GREEN}Mock Token:${NC}       GET http://localhost:3001/auth/debug/token"
    echo -e "  ${GREEN}Mock Sensor:${NC}      GET http://localhost:3003/debug/mock-data"
    
    echo -e "\n${BLUE}📝 Useful Commands:${NC}"
    echo "  View logs:         docker-compose -f docker-compose.debug.yml logs -f"
    echo "  View service logs: docker logs debug-<service> -f"
    echo "  Stop all:          docker-compose -f docker-compose.debug.yml down"
    echo "  Restart service:   docker restart debug-<service>"
    
    echo -e "\n${BLUE}🔑 Debug Tokens:${NC}"
    echo "  Auth Token:        Bearer debug-token"
    echo "  Sensor Token:      debug-token"
    
    echo -e "\n${YELLOW}💡 Tips:${NC}"
    echo "  - All CORS restrictions are disabled"
    echo "  - Mock data is generated every 5 seconds"
    echo "  - SQL queries are logged to console"
    echo "  - Request/response bodies are fully logged"
    echo "  - Test endpoints bypass authentication"
}

# Function to create test data
create_test_data() {
    echo -e "\n${YELLOW}Creating test data...${NC}"
    
    # Create test user
    curl -s -X POST http://localhost:3001/auth/debug/create-test-users \
        -H "Content-Type: application/json" \
        -d '{"count": 5}' > /dev/null 2>&1 || true
    
    # Generate mock sensor data
    curl -s -X POST http://localhost:3003/debug/generate-mock-data \
        -H "Content-Type: application/json" \
        -d '{"type": "all", "count": 100}' > /dev/null 2>&1 || true
    
    echo -e "${GREEN}✅ Test data created${NC}"
}

# Main execution
main() {
    check_prerequisites
    cleanup
    start_services
    wait_for_services
    create_test_data
    show_status
    
    echo -e "\n${GREEN}================================================${NC}"
    echo -e "${GREEN}     Debug server is ready for frontend!${NC}"
    echo -e "${GREEN}     Open http://localhost:9999 to monitor${NC}"
    echo -e "${GREEN}================================================${NC}"
    
    # Optionally tail logs
    read -p "Do you want to see live logs? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose -f docker-compose.debug.yml logs -f
    fi
}

# Handle script termination
trap cleanup EXIT

# Run main function
main