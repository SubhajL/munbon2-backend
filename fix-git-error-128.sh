#!/bin/bash

# Fix for GitHub Actions deployment error 128
# Run this on EC2 to clean up and prepare for deployment

echo "=== Fixing Git Error 128 on EC2 ==="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${YELLOW}This script will fix the Git error and manually deploy${NC}"
echo ""

# Navigate to home directory
cd ~

# Backup any local changes
if [ -d "munbon2-backend" ]; then
    echo -e "${BLUE}Backing up existing directory...${NC}"
    mv munbon2-backend munbon2-backend.backup.$(date +%Y%m%d_%H%M%S)
fi

# Clone fresh repository
echo -e "${BLUE}Cloning fresh repository...${NC}"
git clone https://github.com/SubhajL/munbon2-backend.git
cd munbon2-backend

# Copy environment file
echo -e "${BLUE}Setting up environment...${NC}"
cp .env.ec2 .env

# Stop any existing containers
echo -e "${BLUE}Stopping any existing containers...${NC}"
docker-compose -f docker-compose.ec2-consolidated.yml down 2>/dev/null || true

# Build and start services
echo -e "${BLUE}Building and starting services...${NC}"
docker-compose -f docker-compose.ec2-consolidated.yml up -d --build

# Wait for services to start
echo -e "${BLUE}Waiting for services to start...${NC}"
sleep 30

# Check status
echo -e "${GREEN}=== Service Status ===${NC}"
docker-compose -f docker-compose.ec2-consolidated.yml ps

# Check consumer logs
echo -e "${GREEN}=== Consumer Logs ===${NC}"
docker-compose -f docker-compose.ec2-consolidated.yml logs --tail 20 sensor-data-consumer

echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo ""
echo "Check the services:"
echo "- Consumer Dashboard: http://${EC2_HOST:-43.208.201.191}:3004"
echo "- Sensor Data API: http://${EC2_HOST:-43.208.201.191}:3003"
echo ""
echo "To see live logs:"
echo "docker-compose -f docker-compose.ec2-consolidated.yml logs -f sensor-data-consumer"