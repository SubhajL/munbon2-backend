#!/bin/bash

# Deploy ROS service to EC2 with correct platform
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

echo -e "${BLUE}=== DEPLOYING ROS SERVICE TO EC2 (AMD64 BUILD) ===${NC}"

# Step 1: Check SSH key
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}Error: SSH key not found at $SSH_KEY${NC}"
    echo "Please update the SSH_KEY path in this script"
    exit 1
fi

# Step 2: Build Docker image for AMD64 platform
echo -e "\n${BLUE}Step 1: Building Docker image for AMD64...${NC}"
docker buildx build --platform linux/amd64 -f Dockerfile.simple -t ros-service:latest-amd64 --load .

# Step 3: Save Docker image
echo -e "\n${BLUE}Step 2: Saving Docker image...${NC}"
docker save ros-service:latest-amd64 | gzip > ros-service-amd64.tar.gz
IMAGE_SIZE=$(ls -lh ros-service-amd64.tar.gz | awk '{print $5}')
echo -e "${GREEN}Image saved: $IMAGE_SIZE${NC}"

# Step 4: Clean up existing deployment on EC2
echo -e "\n${BLUE}Step 3: Cleaning up EC2...${NC}"
ssh -i "$SSH_KEY" $EC2_USER@$EC2_HOST << 'EOF'
cd ~/services/ros
docker-compose down 2>/dev/null || true
docker stop ros-service ros-redis 2>/dev/null || true
docker rm ros-service ros-redis 2>/dev/null || true
docker rmi ros-service:latest 2>/dev/null || true
EOF

# Step 5: Copy files to EC2
echo -e "\n${BLUE}Step 4: Copying files to EC2...${NC}"
scp -i "$SSH_KEY" ros-service-amd64.tar.gz $EC2_USER@$EC2_HOST:~/services/ros/
scp -i "$SSH_KEY" docker-compose.ec2.yml $EC2_USER@$EC2_HOST:~/services/ros/docker-compose.yml
scp -i "$SSH_KEY" .env.production $EC2_USER@$EC2_HOST:~/services/ros/.env

# Step 6: Load image and update configuration
echo -e "\n${BLUE}Step 5: Loading image on EC2...${NC}"
ssh -i "$SSH_KEY" $EC2_USER@$EC2_HOST << 'EOF'
cd ~/services/ros
echo "Loading Docker image..."
docker load < ros-service-amd64.tar.gz
# Tag the image correctly
docker tag ros-service:latest-amd64 ros-service:latest
# Update docker-compose to use image instead of build
sed -i 's/build: ./image: ros-service:latest/g' docker-compose.yml
EOF

# Step 7: Start service on EC2
echo -e "\n${BLUE}Step 6: Starting service on EC2...${NC}"
ssh -i "$SSH_KEY" $EC2_USER@$EC2_HOST << 'EOF'
cd ~/services/ros
echo "Starting services..."
docker-compose up -d

echo "Waiting for service to start..."
sleep 15

echo "Checking service status..."
docker-compose ps
echo ""
echo "Service logs:"
docker-compose logs --tail=30 ros-service
EOF

# Step 8: Test the service
echo -e "\n${BLUE}Step 7: Testing service...${NC}"
echo "Testing health endpoint..."
sleep 5
curl -s http://$EC2_HOST:3047/health | jq . || echo "Service may still be starting..."

# Clean up local files
rm -f ros-service-amd64.tar.gz

echo -e "\n${GREEN}✅ Deployment complete!${NC}"
echo -e "${BLUE}Service endpoints:${NC}"
echo "  Health: http://$EC2_HOST:3047/health"
echo "  API: http://$EC2_HOST:3047/api/v1"
echo "  Plot water demand: http://$EC2_HOST:3047/api/v1/demand/plot/{plotId}/calculate"
echo "  Zone water demand: http://$EC2_HOST:3047/api/v1/demand/zone/{zoneId}/calculate"
echo ""
echo -e "${YELLOW}To check logs:${NC}"
echo "  ssh -i $SSH_KEY $EC2_USER@$EC2_HOST 'cd ~/services/ros && docker-compose logs -f ros-service'"