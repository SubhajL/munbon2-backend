#!/bin/bash

# Deploy ROS service to EC2
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# EC2 details
EC2_HOST="${EC2_HOST:-43.208.201.191}"
EC2_USER="ubuntu"
SSH_KEY="$HOME/dev/th-lab01.pem"

echo -e "${BLUE}=== DEPLOYING ROS SERVICE TO EC2 ===${NC}"

# Step 1: Check SSH key
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}Error: SSH key not found at $SSH_KEY${NC}"
    echo "Please update the SSH_KEY path in this script"
    exit 1
fi

# Step 2: Build Docker image locally
echo -e "\n${BLUE}Step 1: Building Docker image...${NC}"
docker build -t ros-service:latest .

# Step 3: Save Docker image
echo -e "\n${BLUE}Step 2: Saving Docker image...${NC}"
docker save ros-service:latest | gzip > ros-service.tar.gz
IMAGE_SIZE=$(ls -lh ros-service.tar.gz | awk '{print $5}')
echo -e "${GREEN}Image saved: $IMAGE_SIZE${NC}"

# Step 4: Create deployment directory on EC2
echo -e "\n${BLUE}Step 3: Preparing EC2...${NC}"
ssh -i "$SSH_KEY" $EC2_USER@$EC2_HOST << 'EOF'
mkdir -p ~/services/ros
cd ~/services/ros
# Stop existing service if running
docker-compose down 2>/dev/null || true
EOF

# Step 5: Copy files to EC2
echo -e "\n${BLUE}Step 4: Copying files to EC2...${NC}"
scp -i "$SSH_KEY" ros-service.tar.gz $EC2_USER@$EC2_HOST:~/services/ros/
scp -i "$SSH_KEY" docker-compose.ec2.yml $EC2_USER@$EC2_HOST:~/services/ros/docker-compose.yml
scp -i "$SSH_KEY" .env.production $EC2_USER@$EC2_HOST:~/services/ros/.env

# Step 6: Load image and start service on EC2
echo -e "\n${BLUE}Step 5: Starting service on EC2...${NC}"
ssh -i "$SSH_KEY" $EC2_USER@$EC2_HOST << 'EOF'
cd ~/services/ros
echo "Loading Docker image..."
docker load < ros-service.tar.gz

echo "Starting services..."
docker-compose up -d

echo "Waiting for service to start..."
sleep 10

echo "Checking service status..."
docker-compose ps
docker-compose logs --tail=20 ros-service
EOF

# Step 7: Test the service
echo -e "\n${BLUE}Step 6: Testing service...${NC}"
echo "Testing health endpoint..."
curl -s http://$EC2_HOST:3047/health | jq . || echo "Service may still be starting..."

# Clean up local files
rm -f ros-service.tar.gz

echo -e "\n${GREEN}✅ Deployment complete!${NC}"
echo -e "${BLUE}Service endpoints:${NC}"
echo "  Health: http://$EC2_HOST:3047/health"
echo "  API: http://$EC2_HOST:3047/api/v1"
echo ""
echo -e "${YELLOW}To check logs:${NC}"
echo "  ssh -i $SSH_KEY $EC2_USER@$EC2_HOST 'cd ~/services/ros && docker-compose logs -f ros-service'"