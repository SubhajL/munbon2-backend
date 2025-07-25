#!/bin/bash

# Simple deployment script using SCP
# Usage: ./deploy-to-ec2-simple.sh

set -e

# Configuration
EC2_IP="43.209.12.182"
SSH_KEY="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"
EC2_USER="ubuntu"
REMOTE_DIR="/home/ubuntu/munbon2-backend"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Deploying to EC2 at $EC2_IP...${NC}"

# Create remote directory
echo -e "${BLUE}Creating remote directory...${NC}"
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" "mkdir -p $REMOTE_DIR"

# Copy files (excluding node_modules and large files)
echo -e "${BLUE}Copying files to EC2...${NC}"
rsync -avz --exclude 'node_modules' \
  --exclude '.git' \
  --exclude '*.log' \
  --exclude '.env' \
  --exclude 'GIS_moonbon' \
  --exclude '*.dbf' \
  --exclude '*.shp' \
  --exclude '*.pdf' \
  -e "ssh -o StrictHostKeyChecking=no -i $SSH_KEY" \
  ./ "$EC2_USER@$EC2_IP:$REMOTE_DIR/"

# Setup on remote
echo -e "${BLUE}Setting up services on EC2...${NC}"
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
cd /home/ubuntu/munbon2-backend

# Start Docker services
echo "Starting Docker services..."
docker-compose up -d postgres redis influxdb

# Wait for databases
echo "Waiting for databases..."
sleep 10

# Install dependencies and start services
SERVICES=("sensor-data" "auth" "gis")
for service in "${SERVICES[@]}"; do
    if [ -d "services/$service" ]; then
        echo "Installing dependencies for $service..."
        cd "services/$service"
        npm install
        cd ../..
    fi
done

# Create PM2 ecosystem file
cat > ecosystem.config.js << 'EOFPM2'
module.exports = {
  apps: [
    {
      name: 'sensor-data',
      cwd: './services/sensor-data',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: 3001
      }
    },
    {
      name: 'auth',
      cwd: './services/auth',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: 3002
      }
    },
    {
      name: 'gis',
      cwd: './services/gis',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: 3006
      }
    }
  ]
}
EOFPM2

# Start with PM2
pm2 delete all || true
pm2 start ecosystem.config.js
pm2 save

echo "Deployment complete!"
pm2 status
EOF

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\nServices should be running at:"
echo -e "- Sensor Data: http://$EC2_IP:3001"
echo -e "- Auth Service: http://$EC2_IP:3002"
echo -e "- GIS Service: http://$EC2_IP:3006"