#!/bin/bash

# Flow Monitoring Service - Direct EC2 Deployment Script
# This script builds the image directly on EC2 to avoid slow local builds
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Flow Monitoring Service direct deployment to EC2...${NC}"

# Configuration
SERVICE_NAME="flow-monitoring"
EC2_HOST="43.209.22.250"
EC2_USER="ubuntu"
EC2_PATH="/home/ubuntu/munbon2-backend/services/flow-monitoring"

# Check if we're in the right directory
if [ ! -f "Dockerfile" ]; then
    echo -e "${RED}Error: Dockerfile not found. Please run this script from the flow-monitoring directory.${NC}"
    exit 1
fi

# Step 1: Create directory structure on EC2
echo -e "${YELLOW}Creating directory structure on EC2...${NC}"
ssh -i ~/dev/th-lab01.pem ${EC2_USER}@${EC2_HOST} "mkdir -p ${EC2_PATH}/src"

# Step 2: Copy all necessary files to EC2
echo -e "${YELLOW}Copying files to EC2...${NC}"
# Copy all Python source files
scp -i ~/dev/th-lab01.pem -r src/* ${EC2_USER}@${EC2_HOST}:${EC2_PATH}/src/
# Copy Docker and requirements files
scp -i ~/dev/th-lab01.pem Dockerfile requirements.txt ${EC2_USER}@${EC2_HOST}:${EC2_PATH}/
# Copy environment and config files
scp -i ~/dev/th-lab01.pem .env.ec2 ${EC2_USER}@${EC2_HOST}:${EC2_PATH}/.env
scp -i ~/dev/th-lab01.pem canal_geometry_template.json ${EC2_USER}@${EC2_HOST}:${EC2_PATH}/

# Step 3: Copy docker-compose snippet
echo -e "${YELLOW}Copying docker-compose configuration...${NC}"
scp -i ~/dev/th-lab01.pem docker-compose.ec2.snippet.yml ${EC2_USER}@${EC2_HOST}:${EC2_PATH}/

# Step 4: Build and deploy on EC2
echo -e "${YELLOW}Building and deploying on EC2...${NC}"
ssh -i ~/dev/th-lab01.pem ${EC2_USER}@${EC2_HOST} << 'ENDSSH'
cd /home/ubuntu/munbon2-backend/services/flow-monitoring

# Build the Docker image locally on EC2
echo "Building Docker image..."
docker build -t munbon-flow-monitoring:latest .

# Update docker-compose.ec2.yml with the correct configuration
echo "Updating docker-compose configuration..."
cd /home/ubuntu/munbon2-backend

# Backup the current docker-compose.ec2.yml
cp docker-compose.ec2.yml docker-compose.ec2.yml.backup

# Update the flow-monitoring service section
# Using sed to replace the service configuration
cat > /tmp/flow-monitoring-update.sh << 'EOF'
#!/bin/bash
# Read the snippet file
SNIPPET=$(cat /home/ubuntu/munbon2-backend/services/flow-monitoring/docker-compose.ec2.snippet.yml)

# Update docker-compose.ec2.yml
# This is a simplified approach - in production, use a proper YAML parser
echo "Please manually update the flow-monitoring service in docker-compose.ec2.yml with:"
echo "----------------------------------------"
cat /home/ubuntu/munbon2-backend/services/flow-monitoring/docker-compose.ec2.snippet.yml
echo "----------------------------------------"
echo "The key change is: PORT 3011 (not 3014)"
EOF

bash /tmp/flow-monitoring-update.sh

# For now, let's use the local image
sed -i 's|image: subhaj888/munbon-flow-monitoring:latest|image: munbon-flow-monitoring:latest|g' docker-compose.ec2.yml

# Stop existing service
docker-compose -f docker-compose.ec2.yml stop flow-monitoring || true

# Remove old container
docker-compose -f docker-compose.ec2.yml rm -f flow-monitoring || true

# Start updated service
echo "Starting Flow Monitoring Service..."
docker-compose -f docker-compose.ec2.yml up -d flow-monitoring

# Wait for service to start
sleep 15

# Check if service is running
echo "Checking service status..."
docker ps | grep flow-monitoring

# Check health
echo "Testing health endpoint..."
if curl -f http://localhost:3011/health; then
    echo -e "\nHealth check passed!"
else
    echo -e "\nHealth check failed. Checking logs..."
    docker logs --tail 50 munbon-flow-monitoring
fi

# Show API endpoints
echo -e "\nTesting API endpoints..."
curl http://localhost:3011/ || true
echo ""
ENDSSH

echo -e "${GREEN}Deployment completed!${NC}"
echo -e "Service should be accessible at: http://${EC2_HOST}:3011"
echo -e "\nUseful commands:"
echo -e "- Check logs: ssh -i ~/dev/th-lab01.pem ${EC2_USER}@${EC2_HOST} 'docker logs -f munbon-flow-monitoring'"
echo -e "- Check status: ssh -i ~/dev/th-lab01.pem ${EC2_USER}@${EC2_HOST} 'docker ps | grep flow-monitoring'"
echo -e "- Test health: curl http://${EC2_HOST}:3011/health"