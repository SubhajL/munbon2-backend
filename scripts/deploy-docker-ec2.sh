#!/bin/bash

# Docker Deployment Script for EC2
# Usage: ./deploy-docker-ec2.sh

set -e

# Configuration
EC2_IP="${EC2_IP:-43.209.12.182}"
SSH_KEY="${SSH_KEY:-/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem}"
EC2_USER="${EC2_USER:-ubuntu}"
REMOTE_DIR="/home/ubuntu/munbon2-backend"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=== Docker Deployment to EC2 ===${NC}"
echo "EC2 Instance: $EC2_IP"
echo "Remote Directory: $REMOTE_DIR"
echo ""

# Check if SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}Error: SSH key not found at $SSH_KEY${NC}"
    exit 1
fi

# Create remote deployment script
cat > /tmp/deploy-docker-remote.sh << 'EOF'
#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install Docker if not present
if ! command_exists docker; then
    echo -e "${BLUE}Installing Docker...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    
    # Start Docker service
    sudo systemctl start docker
    sudo systemctl enable docker
    
    echo -e "${GREEN}Docker installed successfully${NC}"
    echo -e "${YELLOW}Note: You may need to log out and back in for group changes${NC}"
fi

# Install Docker Compose if not present
if ! command_exists docker-compose; then
    echo -e "${BLUE}Installing Docker Compose...${NC}"
    sudo apt-get update
    sudo apt-get install -y docker-compose-plugin
    
    # Create docker-compose command alias
    echo 'alias docker-compose="docker compose"' >> ~/.bashrc
    source ~/.bashrc
fi

# Pull latest code
echo -e "${BLUE}Updating code from repository...${NC}"
git pull origin main || {
    echo -e "${RED}Failed to pull latest code${NC}"
    exit 1
}

# Stop PM2 if running (migration from PM2 to Docker)
if command_exists pm2; then
    echo -e "${BLUE}Stopping PM2 processes...${NC}"
    pm2 stop all || true
    pm2 delete all || true
    # Optionally disable PM2 startup
    pm2 unstartup || true
fi

# Create .env.ec2 if not exists
if [ ! -f ".env.ec2" ]; then
    echo -e "${YELLOW}Creating .env.ec2 from template...${NC}"
    cp .env.ec2.example .env.ec2
    echo -e "${YELLOW}⚠️  Please update .env.ec2 with production values!${NC}"
fi

# Stop existing containers
echo -e "${BLUE}Stopping existing containers...${NC}"
sudo docker compose -f docker-compose.ec2.yml down || true

# Clean up to save disk space
echo -e "${BLUE}Cleaning up Docker resources...${NC}"
sudo docker system prune -f --volumes || true

# Build services
echo -e "${BLUE}Building Docker images...${NC}"
sudo docker compose -f docker-compose.ec2.yml build

# Start services
echo -e "${BLUE}Starting services...${NC}"
sudo docker compose -f docker-compose.ec2.yml up -d

# Wait for services
echo -e "${BLUE}Waiting for services to start...${NC}"
sleep 30

# Show container status
echo -e "\n${BLUE}Container Status:${NC}"
sudo docker compose -f docker-compose.ec2.yml ps

# Health checks
echo -e "\n${BLUE}Service Health Checks:${NC}"
services=(
    "sensor-data:3001"
    "auth:3002"
    "moisture-monitoring:3003"
    "weather-monitoring:3004"
    "water-level-monitoring:3005"
    "gis:3006"
    "rid-ms:3011"
    "ros:3012"
    "awd-control:3013"
    "flow-monitoring:3014"
)

failed_services=()
for service in "${services[@]}"; do
    IFS=':' read -r name port <<< "$service"
    printf "%-25s" "$name (port $port):"
    if timeout 5 curl -f -s "http://localhost:$port/health" > /dev/null 2>&1; then
        echo -e " ${GREEN}✓ Healthy${NC}"
    else
        echo -e " ${RED}✗ Not responding${NC}"
        failed_services+=("$name")
    fi
done

# Show logs for failed services
if [ ${#failed_services[@]} -gt 0 ]; then
    echo -e "\n${RED}Failed services detected. Showing logs:${NC}"
    for service in "${failed_services[@]}"; do
        echo -e "\n${YELLOW}=== Logs for $service ===${NC}"
        sudo docker compose -f docker-compose.ec2.yml logs --tail=30 "$service"
    done
fi

# Setup Docker restart policy
echo -e "\n${BLUE}Configuring Docker to start on boot...${NC}"
sudo systemctl enable docker

# Display access information
echo -e "\n${GREEN}=== Deployment Complete ===${NC}"
echo -e "${BLUE}Service URLs:${NC}"
echo "• Sensor Data:         http://$(curl -s ifconfig.me):3001"
echo "• Auth Service:        http://$(curl -s ifconfig.me):3002"
echo "• Moisture Monitor:    http://$(curl -s ifconfig.me):3003"
echo "• Weather Monitor:     http://$(curl -s ifconfig.me):3004"
echo "• Water Level Monitor: http://$(curl -s ifconfig.me):3005"
echo "• GIS Service:         http://$(curl -s ifconfig.me):3006"
echo "• RID-MS:              http://$(curl -s ifconfig.me):3011"
echo "• ROS:                 http://$(curl -s ifconfig.me):3012"
echo "• AWD Control:         http://$(curl -s ifconfig.me):3013"
echo "• Flow Monitoring:     http://$(curl -s ifconfig.me):3014"

echo -e "\n${BLUE}Useful Docker commands:${NC}"
echo "• View logs:        sudo docker compose -f docker-compose.ec2.yml logs -f [service-name]"
echo "• Restart service:  sudo docker compose -f docker-compose.ec2.yml restart [service-name]"
echo "• Stop all:         sudo docker compose -f docker-compose.ec2.yml down"
echo "• Start all:        sudo docker compose -f docker-compose.ec2.yml up -d"
echo "• View status:      sudo docker compose -f docker-compose.ec2.yml ps"
EOF

# Copy script to EC2
echo -e "${BLUE}Copying deployment script to EC2...${NC}"
scp -o StrictHostKeyChecking=no -i "$SSH_KEY" /tmp/deploy-docker-remote.sh "$EC2_USER@$EC2_IP:~/"

# Execute deployment
echo -e "${BLUE}Executing deployment on EC2...${NC}"
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" 'bash ~/deploy-docker-remote.sh'

# Cleanup
rm /tmp/deploy-docker-remote.sh

echo -e "\n${GREEN}Deployment script completed!${NC}"
echo -e "${BLUE}You can monitor the services by SSHing into the EC2 instance:${NC}"
echo "ssh -i $SSH_KEY $EC2_USER@$EC2_IP"