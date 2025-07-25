#!/bin/bash

# Manual EC2 deployment script that can be run on EC2 instance

echo "=== Manual EC2 Deployment Script ==="
echo ""
echo "This script should be run on your EC2 instance (43.209.12.182)"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Function to check command status
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $1${NC}"
    else
        echo -e "${RED}❌ $1${NC}"
        exit 1
    fi
}

# Step 1: Clone or update repository
echo -e "${BLUE}Step 1: Updating repository...${NC}"
if [ -d "munbon2-backend" ]; then
    cd munbon2-backend
    git pull origin main
    check_status "Repository updated"
else
    git clone https://github.com/SubhajL/munbon2-backend.git
    check_status "Repository cloned"
    cd munbon2-backend
fi

# Step 2: Install Docker if not installed
echo -e "${BLUE}Step 2: Checking Docker installation...${NC}"
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo -e "${YELLOW}Please logout and login again for docker group to take effect${NC}"
    exit 1
else
    echo -e "${GREEN}✅ Docker is installed${NC}"
fi

# Step 3: Install Docker Compose if not installed
echo -e "${BLUE}Step 3: Checking Docker Compose installation...${NC}"
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    check_status "Docker Compose installed"
else
    echo -e "${GREEN}✅ Docker Compose is installed${NC}"
fi

# Step 4: Setup environment
echo -e "${BLUE}Step 4: Setting up environment...${NC}"
if [ ! -f ".env" ]; then
    cp .env.ec2 .env
    check_status "Environment file created"
else
    echo -e "${GREEN}✅ Environment file exists${NC}"
fi

# Step 5: Initialize database
echo -e "${BLUE}Step 5: Initializing database...${NC}"
# Check if PostgreSQL container is running
if docker ps | grep -q munbon-postgres; then
    echo "PostgreSQL is running"
    # Create sensor_data database if it doesn't exist
    docker exec munbon-postgres psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'sensor_data'" | grep -q 1 || {
        docker exec munbon-postgres psql -U postgres -c "CREATE DATABASE sensor_data;"
        docker exec munbon-postgres psql -U postgres -d sensor_data -c "CREATE EXTENSION IF NOT EXISTS postgis;"
        docker exec munbon-postgres psql -U postgres -d sensor_data -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
        check_status "Database initialized"
    }
else
    echo -e "${YELLOW}PostgreSQL not running yet, will be started with docker-compose${NC}"
fi

# Step 6: Deploy services
echo -e "${BLUE}Step 6: Deploying services with Docker Compose...${NC}"
docker-compose -f docker-compose.ec2-consolidated.yml down
docker-compose -f docker-compose.ec2-consolidated.yml up -d --build
check_status "Services deployed"

# Step 7: Wait for services to start
echo -e "${BLUE}Step 7: Waiting for services to start...${NC}"
sleep 30

# Step 8: Health checks
echo -e "${BLUE}Step 8: Performing health checks...${NC}"
services=(
    "localhost:5432:PostgreSQL"
    "localhost:3001:Sensor-Data"
    "localhost:3002:Consumer-Dashboard"
)

for service in "${services[@]}"; do
    IFS=':' read -r host port name <<< "$service"
    printf "Checking $name... "
    if nc -zv $host $port 2>/dev/null; then
        echo -e "${GREEN}✅ Available${NC}"
    else
        echo -e "${RED}❌ Not responding${NC}"
    fi
done

# Step 9: Show logs
echo -e "${BLUE}Step 9: Service status...${NC}"
docker-compose -f docker-compose.ec2-consolidated.yml ps

echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Services should be available at:"
echo "- Sensor Data API: http://43.209.12.182:3001"
echo "- Consumer Dashboard: http://43.209.12.182:3002"
echo ""
echo "To view logs:"
echo "docker-compose -f docker-compose.ec2-consolidated.yml logs -f"
echo ""
echo "To restart services:"
echo "docker-compose -f docker-compose.ec2-consolidated.yml restart"