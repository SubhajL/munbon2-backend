#!/bin/bash

# Deploy ROS/GIS Integration Service using Docker on EC2 (Build on EC2)

set -e

# Configuration
EC2_HOST="43.209.22.250"
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

echo -e "${GREEN}Deploying ROS/GIS Integration Service with Docker (Remote Build)${NC}"
echo ""

# Step 1: Create directory on EC2
echo -e "${YELLOW}Step 1: Creating directory on EC2...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} "mkdir -p ${REMOTE_DIR}"

# Step 2: Copy all necessary files to EC2
echo -e "${YELLOW}Step 2: Copying files to EC2...${NC}"
rsync -avz -e "ssh -i ${SSH_KEY}" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.env' \
  --exclude='venv' \
  --exclude='.pytest_cache' \
  --exclude='.coverage' \
  --exclude='.git' \
  ./Dockerfile ./docker-compose.yml ./requirements.txt ./src ./migrations ./scripts \
  ${EC2_USER}@${EC2_HOST}:${REMOTE_DIR}/

# Step 3: Check if munbon-network exists, create if not
echo -e "${YELLOW}Step 3: Checking Docker network...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} << 'EOF'
if ! docker network ls | grep -q munbon-network; then
    echo "Creating munbon-network..."
    docker network create munbon-network
else
    echo "munbon-network already exists"
fi
EOF

# Step 4: Build Docker image on EC2
echo -e "${YELLOW}Step 4: Building Docker image on EC2...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} << EOF
cd ${REMOTE_DIR}
docker build -t ${SERVICE_NAME}:latest .
EOF

# Step 5: Update docker-compose.yml for EC2 environment
echo -e "${YELLOW}Step 5: Updating configuration for EC2 environment...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} << EOF
cd ${REMOTE_DIR}

# Create updated docker-compose.yml with proper networking
cat > docker-compose.yml << 'COMPOSE'
version: '3.8'

services:
  ros-gis-integration:
    image: ros-gis-integration:latest
    container_name: ros-gis-integration
    restart: unless-stopped
    ports:
      - "3022:3022"
    environment:
      # Database Configuration
      POSTGRES_URL: "postgresql://postgres:P@ssw0rd123!@timescaledb:5432/munbon_dev"
      REDIS_URL: "redis://ros-redis:6379/2"
      
      # Service Configuration
      ENVIRONMENT: "production"
      LOG_LEVEL: "INFO"
      USE_MOCK_SERVER: "false"
      
      # External Services
      ROS_SERVICE_URL: "http://ros-service:3047"
      GIS_SERVICE_URL: "http://host.docker.internal:3007"
      FLOW_MONITORING_URL: "http://host.docker.internal:3011"
      SCHEDULER_SERVICE_URL: "http://host.docker.internal:3021"
      
      # Service Settings
      DEMAND_COMBINATION_STRATEGY: "aquacrop_priority"
      CACHE_TTL_SECONDS: "300"
    
    networks:
      - munbon-network
      - postgresql_docker_default
    
    extra_hosts:
      - "host.docker.internal:host-gateway"
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3022/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

networks:
  munbon-network:
    external: true
  postgresql_docker_default:
    external: true
COMPOSE
EOF

# Step 6: Stop and remove existing container if running
echo -e "${YELLOW}Step 6: Stopping existing container if running...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} << EOF
cd ${REMOTE_DIR}
docker-compose down || true
EOF

# Step 7: Start the service with Docker Compose
echo -e "${YELLOW}Step 7: Starting service with Docker Compose...${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} << EOF
cd ${REMOTE_DIR}
docker-compose up -d
EOF

# Step 8: Wait for service to start
echo -e "${YELLOW}Step 8: Waiting for service to start...${NC}"
sleep 20

# Step 9: Verify deployment
echo -e "${YELLOW}Step 9: Verifying deployment...${NC}"

# Check container status
echo -e "${YELLOW}Container status:${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} "docker ps | grep ${SERVICE_NAME}" || echo "Container not running"

# Check container logs
echo -e "${YELLOW}Recent logs:${NC}"
ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} "cd ${REMOTE_DIR} && docker-compose logs --tail=20"

# Test health endpoint
echo -e "${YELLOW}Testing health endpoint...${NC}"
HEALTH_CHECK=$(ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} "curl -s http://localhost:${SERVICE_PORT}/health" 2>/dev/null || echo "Failed")

if [[ $HEALTH_CHECK == *"healthy"* ]]; then
    echo -e "${GREEN}✓ Service deployed successfully!${NC}"
    echo ""
    echo "$HEALTH_CHECK" | python3 -m json.tool
else
    echo -e "${YELLOW}⚠ Service may still be starting or there's an issue. Check logs:${NC}"
    ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} "cd ${REMOTE_DIR} && docker-compose logs --tail=50"
fi

echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo ""
echo "Useful commands:"
echo "  View logs: ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} 'cd ${REMOTE_DIR} && docker-compose logs -f'"
echo "  Restart: ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} 'cd ${REMOTE_DIR} && docker-compose restart'"
echo "  Stop: ssh -i ${SSH_KEY} ${EC2_USER}@${EC2_HOST} 'cd ${REMOTE_DIR} && docker-compose down'"
echo ""
echo "Once security group is updated, access at:"
echo "  http://${EC2_HOST}:${SERVICE_PORT}/health"
echo "  http://${EC2_HOST}:${SERVICE_PORT}/graphql"
echo ""