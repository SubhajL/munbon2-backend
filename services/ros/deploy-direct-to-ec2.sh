#!/bin/bash

# Direct deployment to EC2 without Docker
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

echo -e "${BLUE}=== DIRECT DEPLOYMENT OF ROS SERVICE TO EC2 ===${NC}"

# Step 1: Create deployment archive
echo -e "\n${BLUE}Step 1: Creating deployment archive...${NC}"
tar czf ros-service.tar.gz \
  --exclude=node_modules \
  --exclude=dist \
  --exclude=.git \
  --exclude=coverage \
  --exclude=.env* \
  package*.json tsconfig.json src/

# Step 2: Copy to EC2
echo -e "\n${BLUE}Step 2: Copying files to EC2...${NC}"
scp -i "$SSH_KEY" ros-service.tar.gz $EC2_USER@$EC2_HOST:~/
scp -i "$SSH_KEY" .env.production $EC2_USER@$EC2_HOST:~/ros-service.env

# Step 3: Setup and run on EC2
echo -e "\n${BLUE}Step 3: Setting up service on EC2...${NC}"
ssh -i "$SSH_KEY" $EC2_USER@$EC2_HOST << 'EOF'
# Stop existing service
pm2 stop ros-service 2>/dev/null || true
pm2 delete ros-service 2>/dev/null || true

# Create service directory
mkdir -p ~/services/ros
cd ~/services/ros

# Extract files
tar xzf ~/ros-service.tar.gz
cp ~/ros-service.env .env

# Install dependencies
echo "Installing dependencies..."
npm ci

# Install global tools
npm install -g pm2 ts-node typescript

# Create PM2 ecosystem file
cat > ecosystem.config.js << 'PM2EOF'
module.exports = {
  apps: [{
    name: 'ros-service',
    script: 'ts-node',
    args: '-r tsconfig-paths/register --transpile-only src/index.ts',
    env: {
      NODE_ENV: 'production',
      PORT: 3047,
      DB_HOST: 'localhost',
      DB_PORT: 5432,
      DB_NAME: 'munbon_dev',
      DB_SCHEMA: 'ros',
      DB_USER: 'postgres',
      DB_PASSWORD: 'P@ssw0rd123!',
      REDIS_HOST: 'localhost',
      REDIS_PORT: 6379
    },
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G'
  }]
};
PM2EOF

# Start with PM2
echo "Starting service with PM2..."
pm2 start ecosystem.config.js

# Save PM2 config
pm2 save
pm2 startup | grep 'sudo' | bash

# Show status
pm2 status
EOF

# Step 4: Test the service
echo -e "\n${BLUE}Step 4: Testing service...${NC}"
sleep 10
echo "Testing health endpoint..."
curl -s http://$EC2_HOST:3047/health | jq . || echo "Service may still be starting..."

# Clean up
rm -f ros-service.tar.gz

echo -e "\n${GREEN}✅ Direct deployment complete!${NC}"
echo -e "${BLUE}Service endpoints:${NC}"
echo "  Health: http://$EC2_HOST:3047/health"
echo "  API: http://$EC2_HOST:3047/api/v1"
echo "  Plot water demand: http://$EC2_HOST:3047/api/v1/demand/plot/{plotId}/calculate"
echo ""
echo -e "${YELLOW}To check logs:${NC}"
echo "  ssh -i $SSH_KEY $EC2_USER@$EC2_HOST 'pm2 logs ros-service'"
echo ""
echo -e "${YELLOW}To restart service:${NC}"
echo "  ssh -i $SSH_KEY $EC2_USER@$EC2_HOST 'pm2 restart ros-service'"