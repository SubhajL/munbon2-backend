#!/bin/bash

# Deploy sensor-location-mapping service to EC2
set -e

# Configuration
EC2_HOST="${EC2_HOST:-43.208.201.191}"
EC2_USER="ubuntu"
SSH_KEY="$HOME/dev/th-lab01.pem"
SERVICE_NAME="sensor-location-mapping"
SERVICE_DIR="/home/ubuntu/munbon2-backend/services/$SERVICE_NAME"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=== Deploying $SERVICE_NAME to EC2 ===${NC}"

# 1. Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}Error: SSH key not found at $SSH_KEY${NC}"
    exit 1
fi

# 2. Build the service locally
echo -e "\n${BLUE}Building service locally...${NC}"
npm run build

# 3. Create deployment package
echo -e "\n${BLUE}Creating deployment package...${NC}"
tar -czf deployment.tar.gz \
    --exclude node_modules \
    --exclude .env \
    --exclude deployment.tar.gz \
    --exclude deploy-to-ec2.sh \
    .

# 4. Copy to EC2
echo -e "\n${BLUE}Copying files to EC2...${NC}"
scp -i "$SSH_KEY" deployment.tar.gz "$EC2_USER@$EC2_HOST:/tmp/"

# 5. Deploy on EC2
echo -e "\n${BLUE}Deploying on EC2...${NC}"
ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << 'REMOTE_SCRIPT'
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SERVICE_NAME="sensor-location-mapping"
SERVICE_DIR="/home/ubuntu/munbon2-backend/services/$SERVICE_NAME"

# Create service directory
echo -e "${YELLOW}Creating service directory...${NC}"
mkdir -p "$SERVICE_DIR"

# Extract deployment package
echo -e "${YELLOW}Extracting deployment package...${NC}"
cd "$SERVICE_DIR"
tar -xzf /tmp/deployment.tar.gz
rm /tmp/deployment.tar.gz

# Copy production environment file
echo -e "${YELLOW}Setting up environment...${NC}"
cp .env.production .env

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
npm ci --production

# Build TypeScript (if dist folder wasn't included)
if [ ! -d "dist" ]; then
    echo -e "${YELLOW}Building TypeScript...${NC}"
    npm install --save-dev typescript @types/node
    npm run build
fi

# Create PM2 ecosystem file if it doesn't exist
if [ ! -f "ecosystem.config.js" ]; then
    echo -e "${YELLOW}Creating PM2 ecosystem config...${NC}"
    cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [{
    name: 'sensor-location-mapping',
    script: './dist/main.js',
    instances: 1,
    exec_mode: 'cluster',
    env: {
      NODE_ENV: 'production',
      PORT: 3018
    },
    error_file: '/home/ubuntu/logs/sensor-location-mapping-error.log',
    out_file: '/home/ubuntu/logs/sensor-location-mapping-out.log',
    log_file: '/home/ubuntu/logs/sensor-location-mapping-combined.log',
    time: true,
    max_memory_restart: '500M',
    autorestart: true,
    max_restarts: 10,
    min_uptime: '10s'
  }]
};
EOF
fi

# Create logs directory
mkdir -p /home/ubuntu/logs

# Start or restart with PM2
echo -e "${YELLOW}Starting service with PM2...${NC}"
pm2 delete sensor-location-mapping 2>/dev/null || true
pm2 start ecosystem.config.js

# Save PM2 configuration
pm2 save

echo -e "\n${GREEN}✓ Deployment complete!${NC}"
echo -e "${YELLOW}Service running on port 3018${NC}"

# Show service status
pm2 status sensor-location-mapping

REMOTE_SCRIPT

# 6. Cleanup local deployment package
rm -f deployment.tar.gz

echo -e "\n${GREEN}=== Deployment Complete ===${NC}"
echo -e "${YELLOW}Service URL: http://$EC2_HOST:3018${NC}"
echo -e "${YELLOW}Health Check: http://$EC2_HOST:3018/health${NC}"

# 7. Test the deployment
echo -e "\n${BLUE}Testing deployment...${NC}"
sleep 5
if curl -s -f "http://$EC2_HOST:3018/health" > /dev/null; then
    echo -e "${GREEN}✓ Health check passed!${NC}"
else
    echo -e "${RED}✗ Health check failed!${NC}"
    echo -e "${YELLOW}Checking logs...${NC}"
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" "pm2 logs sensor-location-mapping --lines 20"
fi