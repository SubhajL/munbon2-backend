#!/bin/bash

# Deploy ROS/GIS Integration Service using Docker on EC2

set -e

# Configuration
EC2_HOST="${EC2_HOST:-43.208.201.191}"
EC2_USER="ubuntu"
SSH_KEY="$HOME/dev/th-lab01.pem"
SERVICE_NAME="ros-gis-integration"
SERVICE_PORT="3022"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Deploying ROS/GIS Integration Service with Docker${NC}"
echo ""

# Step 1: Build Docker image locally
echo -e "${YELLOW}Step 1: Building Docker image locally...${NC}"
docker build -t ${SERVICE_NAME}:latest .

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to build Docker image${NC}"
    exit 1
fi

# Step 2: Save and transfer Docker image
echo -e "${YELLOW}Step 2: Saving and transferring Docker image to EC2...${NC}"
docker save ${SERVICE_NAME}:latest | gzip | ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} "gunzip | docker load"

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to transfer Docker image${NC}"
    exit 1
fi

# Step 3: Copy docker-compose.yml to EC2
echo -e "${YELLOW}Step 3: Copying docker-compose.yml to EC2...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} "mkdir -p /home/ubuntu/services/${SERVICE_NAME}"
scp -i ${SSH_KEY} docker-compose.yml ${EC2_USER}@${EC2_HOST}:/home/ubuntu/services/${SERVICE_NAME}/

# Step 4: Check if munbon-network exists, create if not
echo -e "${YELLOW}Step 4: Checking Docker network...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} << 'EOF'
if ! docker network ls | grep -q munbon-network; then
    echo "Creating munbon-network..."
    docker network create munbon-network
else
    echo "munbon-network already exists"
fi
EOF

# Step 5: Update docker-compose.yml for EC2 environment
echo -e "${YELLOW}Step 5: Updating configuration for EC2 environment...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} << 'EOF'
cd /home/ubuntu/services/ros-gis-integration

# Update host.docker.internal to use the host network mode or actual IPs
sed -i 's/host.docker.internal/172.17.0.1/g' docker-compose.yml

# For ROS service, use the container name if it's in the same network
sed -i 's|http://172.17.0.1:3047|http://ros-service:3047|g' docker-compose.yml
EOF

# Step 6: Stop and remove existing container if running
echo -e "${YELLOW}Step 6: Stopping existing container if running...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} << 'EOF'
cd /home/ubuntu/services/ros-gis-integration
docker-compose down || true
EOF

# Step 7: Start the service with Docker Compose
echo -e "${YELLOW}Step 7: Starting service with Docker Compose...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} << 'EOF'
cd /home/ubuntu/services/ros-gis-integration
docker-compose up -d
EOF

# Step 8: Wait for service to start
echo -e "${YELLOW}Step 8: Waiting for service to start...${NC}"
sleep 20

# Step 9: Verify deployment
echo -e "${YELLOW}Step 9: Verifying deployment...${NC}"

# Check container status
echo -e "${YELLOW}Container status:${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} "docker ps | grep ${SERVICE_NAME}"

# Test health endpoint
echo -e "${YELLOW}Testing health endpoint...${NC}"
HEALTH_CHECK=$(ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} "curl -s http://localhost:${SERVICE_PORT}/health" 2>/dev/null || echo "Failed")

if [[ $HEALTH_CHECK == *"healthy"* ]]; then
    echo -e "${GREEN}✓ Service deployed successfully!${NC}"
    echo ""
    echo "$HEALTH_CHECK" | python3 -m json.tool
else
    echo -e "${YELLOW}⚠ Service may still be starting. Check logs:${NC}"
    echo "  ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} 'cd /home/ubuntu/services/${SERVICE_NAME} && docker-compose logs -f'"
fi

echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo ""
echo "Useful commands:"
echo "  View logs: ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} 'cd /home/ubuntu/services/${SERVICE_NAME} && docker-compose logs -f'"
echo "  Restart: ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} 'cd /home/ubuntu/services/${SERVICE_NAME} && docker-compose restart'"
echo "  Stop: ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} 'cd /home/ubuntu/services/${SERVICE_NAME} && docker-compose down'"
echo ""
echo "Once security group is updated, access at:"
echo "  http://${EC2_HOST}:${SERVICE_PORT}/health"
echo "  http://${EC2_HOST}:${SERVICE_PORT}/graphql"
echo ""