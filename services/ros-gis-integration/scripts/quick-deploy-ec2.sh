#!/bin/bash

# Quick deployment script for ROS/GIS Integration Service to EC2

set -e

# Configuration
EC2_HOST="43.209.22.250"
EC2_USER="ubuntu"
SSH_KEY="$HOME/dev/th-lab01.pem"  # Update this path
SERVICE_NAME="ros-gis-integration"
SERVICE_PORT="3022"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Quick Deploy: ROS/GIS Integration Service${NC}"
echo ""

# Step 1: Deploy database schema
echo -e "${YELLOW}Step 1: Deploying database schema...${NC}"
./scripts/deploy-database-ec2.sh

# Step 2: Build Docker image
echo -e "${YELLOW}Step 2: Building Docker image...${NC}"
docker build -t ${SERVICE_NAME}:latest .

# Step 3: Save and transfer image
echo -e "${YELLOW}Step 3: Transferring Docker image to EC2...${NC}"
docker save ${SERVICE_NAME}:latest | gzip | ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} "gunzip | docker load"

# Step 4: Deploy on EC2
echo -e "${YELLOW}Step 4: Deploying service on EC2...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} << 'EOF'
# Stop existing container if running
docker stop ros-gis-integration 2>/dev/null || true
docker rm ros-gis-integration 2>/dev/null || true

# Run new container
docker run -d \
  --name ros-gis-integration \
  --restart unless-stopped \
  -p 3022:3022 \
  -e POSTGRES_URL="postgresql://postgres:P@ssw0rd123!@host.docker.internal:5432/munbon_dev" \
  -e REDIS_URL="redis://host.docker.internal:6379/2" \
  -e ENVIRONMENT="production" \
  -e USE_MOCK_SERVER="false" \
  -e LOG_LEVEL="INFO" \
  ros-gis-integration:latest

# Wait for service to start
sleep 5

# Check status
docker ps | grep ros-gis-integration
EOF

# Step 5: Verify deployment
echo -e "${YELLOW}Step 5: Verifying deployment...${NC}"
sleep 5

# Health check
HEALTH_CHECK=$(curl -s http://${EC2_HOST}:${SERVICE_PORT}/health | python3 -m json.tool 2>/dev/null || echo "Failed")

if [[ $HEALTH_CHECK == *"healthy"* ]]; then
    echo -e "${GREEN}✓ Service deployed successfully!${NC}"
    echo ""
    echo "Service endpoints:"
    echo "  Health: http://${EC2_HOST}:${SERVICE_PORT}/health"
    echo "  GraphQL: http://${EC2_HOST}:${SERVICE_PORT}/graphql"
    echo "  API Status: http://${EC2_HOST}:${SERVICE_PORT}/api/v1/status"
    echo "  Admin: http://${EC2_HOST}:${SERVICE_PORT}/api/v1/admin/health/detailed"
else
    echo -e "${YELLOW}⚠ Service may still be starting. Check manually:${NC}"
    echo "  ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} docker logs ros-gis-integration"
fi

echo ""
echo "Done!"