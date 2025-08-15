#!/bin/bash

# Flow Monitoring Service - EC2 Deployment Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Flow Monitoring Service deployment to EC2...${NC}"

# Configuration
SERVICE_NAME="flow-monitoring"
DOCKER_IMAGE="subhaj888/munbon-flow-monitoring"
EC2_HOST="43.209.22.250"
EC2_USER="ubuntu"

# Check if we're in the right directory
if [ ! -f "Dockerfile" ]; then
    echo -e "${RED}Error: Dockerfile not found. Please run this script from the flow-monitoring directory.${NC}"
    exit 1
fi

# Step 1: Build Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
docker build -t ${DOCKER_IMAGE}:latest .

# Step 2: Tag image
echo -e "${YELLOW}Tagging image...${NC}"
docker tag ${DOCKER_IMAGE}:latest ${DOCKER_IMAGE}:$(date +%Y%m%d_%H%M%S)

# Step 3: Push to Docker Hub
echo -e "${YELLOW}Pushing image to Docker Hub...${NC}"
docker push ${DOCKER_IMAGE}:latest

# Step 4: Copy environment file to EC2
echo -e "${YELLOW}Copying environment configuration to EC2...${NC}"
scp -i ~/dev/th-lab01.pem .env.ec2 ${EC2_USER}@${EC2_HOST}:/home/ubuntu/munbon2-backend/services/flow-monitoring/.env

# Step 5: Copy network configuration files
echo -e "${YELLOW}Copying network configuration files...${NC}"
scp -i ~/dev/th-lab01.pem src/munbon_network_final.json ${EC2_USER}@${EC2_HOST}:/home/ubuntu/munbon2-backend/services/flow-monitoring/src/
scp -i ~/dev/th-lab01.pem canal_geometry_template.json ${EC2_USER}@${EC2_HOST}:/home/ubuntu/munbon2-backend/services/flow-monitoring/

# Step 6: Update docker-compose on EC2
echo -e "${YELLOW}Updating service on EC2...${NC}"
ssh -i ~/dev/th-lab01.pem ${EC2_USER}@${EC2_HOST} << 'ENDSSH'
cd /home/ubuntu/munbon2-backend

# Pull latest image
docker pull subhaj888/munbon-flow-monitoring:latest

# Stop existing service
docker-compose -f docker-compose.ec2.yml stop flow-monitoring

# Remove old container
docker-compose -f docker-compose.ec2.yml rm -f flow-monitoring

# Start updated service
docker-compose -f docker-compose.ec2.yml up -d flow-monitoring

# Check if service is running
sleep 10
docker ps | grep flow-monitoring

# Check logs
echo "Recent logs:"
docker logs --tail 20 munbon-flow-monitoring

# Check health
echo "Health check:"
curl -f http://localhost:3011/health || echo "Health check failed"
ENDSSH

echo -e "${GREEN}Deployment completed!${NC}"
echo -e "Service should be accessible at: http://${EC2_HOST}:3011"
echo -e "Check logs with: ssh -i ~/dev/th-lab01.pem ${EC2_USER}@${EC2_HOST} 'docker logs munbon-flow-monitoring'"