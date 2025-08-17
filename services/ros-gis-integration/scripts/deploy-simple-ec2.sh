#!/bin/bash

# Simple deployment script for ROS/GIS Integration Service to EC2

set -e

# Configuration
EC2_HOST="${EC2_HOST:-43.208.201.191}"
EC2_USER="ubuntu"
SSH_KEY="$HOME/dev/th-lab01.pem"
SERVICE_NAME="ros-gis-integration"
SERVICE_PORT="3022"
REMOTE_DIR="/home/ubuntu/services/${SERVICE_NAME}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Deploying ROS/GIS Integration Service to EC2${NC}"
echo ""

# Step 1: Create directory structure on EC2
echo -e "${YELLOW}Step 1: Creating directory structure on EC2...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} "mkdir -p ${REMOTE_DIR}"

# Step 2: Copy source files
echo -e "${YELLOW}Step 2: Copying source files to EC2...${NC}"
rsync -avz -e "ssh -i ${SSH_KEY}" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.env' \
  --exclude='venv' \
  --exclude='.pytest_cache' \
  --exclude='.coverage' \
  ./src ./requirements.txt ./scripts \
  ${EC2_USER}@${EC2_HOST}:${REMOTE_DIR}/

# Step 3: Create environment file on EC2
echo -e "${YELLOW}Step 3: Creating environment configuration...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} << 'EOF'
cd /home/ubuntu/services/ros-gis-integration

cat > .env << 'ENV'
# ROS/GIS Integration Service Configuration
POSTGRES_URL=postgresql://postgres:P@ssw0rd123!@localhost:5432/munbon_dev
REDIS_URL=redis://localhost:6379/2
ENVIRONMENT=production
LOG_LEVEL=INFO
USE_MOCK_SERVER=false

# External services (update with actual URLs when available)
ROS_SERVICE_URL=http://localhost:3047
GIS_SERVICE_URL=http://localhost:3007
FLOW_MONITORING_URL=http://localhost:3011
SCHEDULER_SERVICE_URL=http://localhost:3021

# Service configuration
DEMAND_COMBINATION_STRATEGY=aquacrop_priority
CACHE_TTL_SECONDS=300
ENV
EOF

# Step 4: Install Python dependencies
echo -e "${YELLOW}Step 4: Installing Python dependencies...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} << 'EOF'
cd /home/ubuntu/services/ros-gis-integration

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
EOF

# Step 5: Stop existing service if running
echo -e "${YELLOW}Step 5: Stopping existing service...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} << 'EOF'
# Check if running with PM2
pm2 list | grep ros-gis-integration && pm2 delete ros-gis-integration || true

# Check if running as systemd service
sudo systemctl stop ros-gis-integration || true
EOF

# Step 6: Start the service with PM2
echo -e "${YELLOW}Step 6: Starting service with PM2...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} << 'EOF'
cd /home/ubuntu/services/ros-gis-integration

# Start with PM2
pm2 start src/main.py \
  --name ros-gis-integration \
  --interpreter ./venv/bin/python \
  --env production \
  --max-memory-restart 1G

# Save PM2 configuration
pm2 save
pm2 startup | grep sudo | bash
EOF

# Step 7: Verify deployment
echo -e "${YELLOW}Step 7: Verifying deployment...${NC}"
sleep 10

# Check if service is running
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} "pm2 list | grep ros-gis-integration"

# Health check
echo -e "${YELLOW}Checking service health...${NC}"
HEALTH_CHECK=$(curl -s http://${EC2_HOST}:${SERVICE_PORT}/health 2>/dev/null || echo "Failed")

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
    echo "  ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} pm2 logs ros-gis-integration"
fi

echo ""
echo "To view logs:"
echo "  ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} pm2 logs ros-gis-integration"
echo ""
echo "To monitor:"
echo "  ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} pm2 monit"
echo ""
echo "Done!"