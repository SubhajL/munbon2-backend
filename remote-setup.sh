#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Setting up Munbon Backend on EC2...${NC}"

# Update system
sudo apt-get update

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo -e "${BLUE}Installing Docker...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
fi

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    echo -e "${BLUE}Installing Docker Compose...${NC}"
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Install Node.js and PM2 if not present
if ! command -v node &> /dev/null; then
    echo -e "${BLUE}Installing Node.js...${NC}"
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm install 18
    nvm use 18
fi

# Install PM2 globally
if ! command -v pm2 &> /dev/null; then
    npm install -g pm2
fi

# Clone or update repository
cd ~
if [ -d "munbon2-backend" ]; then
    echo -e "${BLUE}Updating existing repository...${NC}"
    cd munbon2-backend
    git pull origin main
else
    echo -e "${BLUE}Cloning repository...${NC}"
    git clone https://github.com/SubhajL/munbon2-backend.git
    cd munbon2-backend
fi

# Copy environment files
echo -e "${BLUE}Setting up environment files...${NC}"
for service in sensor-data auth gis moisture-monitoring rid-ms ros; do
    if [ -d "services/$service" ] && [ -f "services/$service/.env.example" ]; then
        cp "services/$service/.env.example" "services/$service/.env"
        echo "Created .env for $service"
    fi
done

# Start Docker services
echo -e "${BLUE}Starting Docker services...${NC}"
docker-compose up -d postgres redis influxdb

# Wait for databases
echo -e "${BLUE}Waiting for databases...${NC}"
sleep 15

# Install dependencies for each service
SERVICES=("sensor-data" "auth" "gis" "moisture-monitoring" "rid-ms" "ros")
for service in "${SERVICES[@]}"; do
    if [ -d "services/$service" ]; then
        echo -e "${BLUE}Installing dependencies for $service...${NC}"
        cd "services/$service"
        npm install
        cd ../..
    fi
done

# Start services with PM2
echo -e "${BLUE}Starting services with PM2...${NC}"
pm2 delete all || true

# Start each service
cd ~/munbon2-backend
pm2 start services/sensor-data/src/index.ts --name sensor-data --interpreter node_modules/.bin/ts-node
pm2 start services/auth/src/index.ts --name auth --interpreter node_modules/.bin/ts-node  
pm2 start services/gis/src/index.ts --name gis --interpreter node_modules/.bin/ts-node
pm2 start services/moisture-monitoring/src/index.ts --name moisture-monitoring --interpreter node_modules/.bin/ts-node
pm2 start services/rid-ms/src/index.ts --name rid-ms --interpreter node_modules/.bin/ts-node
pm2 start services/ros/src/index.ts --name ros --interpreter node_modules/.bin/ts-node

# Save PM2 configuration
pm2 save
pm2 startup systemd -u $USER --hp /home/$USER | grep sudo | bash

echo -e "${GREEN}Deployment complete!${NC}"
pm2 status
