#!/bin/bash

# Start services with simple approach
# Usage: ./start-services-simple-ec2.sh

set -e

# Configuration
EC2_IP="${EC2_HOST:-43.208.201.191}"
SSH_KEY="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"
EC2_USER="ubuntu"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}Starting services on EC2 with simple approach...${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

# Check if we have tsx and ts-node installed locally
echo -e "${BLUE}Checking for required tools...${NC}"
if ! command -v tsx &> /dev/null; then
    echo "Installing tsx locally..."
    npm install --save-dev tsx
fi

if ! command -v ts-node &> /dev/null; then
    echo "Installing ts-node locally..."
    npm install --save-dev ts-node typescript @types/node
fi

# Stop all PM2 processes
echo -e "${BLUE}Stopping all PM2 processes...${NC}"
pm2 kill

# Start services individually to debug
echo -e "${BLUE}Starting services individually...${NC}"

# Start sensor-data service (port 3003)
echo -e "${YELLOW}Starting sensor-data service...${NC}"
cd services/sensor-data
PORT=3003 HOST=0.0.0.0 pm2 start --name sensor-data "npx ts-node src/cmd/server/main.ts"
cd ../..

# Start auth service (port 3002) - skip due to TypeScript errors
echo -e "${YELLOW}Skipping auth service due to TypeScript errors...${NC}"

# GIS service (port 3007)
echo -e "${YELLOW}Starting gis service...${NC}"
cd services/gis
PORT=3007 HOST=0.0.0.0 DATABASE_URL=postgresql://postgres:postgres123@localhost:5434/gis_db pm2 start --name gis "npx ts-node src/index.ts"
cd ../..

# ROS service (port 3047)
echo -e "${YELLOW}Starting ros service...${NC}"
cd services/ros
PORT=3047 HOST=0.0.0.0 DATABASE_URL=postgresql://postgres:postgres123@localhost:5434/ros_db pm2 start --name ros "npx tsx src/index.ts"
cd ../..

# The monitoring services are already working, just verify
echo -e "${BLUE}Monitoring services should already be running...${NC}"

# Wait for services to start
sleep 10

# Check PM2 status
echo -e "\n${GREEN}PM2 Status:${NC}"
pm2 status

# Check all ports
echo -e "\n${GREEN}Service port status:${NC}"
echo -e "${YELLOW}Port   Service                    Status${NC}"
echo -e "${YELLOW}----   ----------------------     ------${NC}"

ports=("3002:auth" "3003:sensor-data" "3005:moisture-monitoring" "3006:weather-monitoring" 
       "3007:gis" "3008:water-level-monitoring" "3010:awd-control" "3014:flow-monitoring" 
       "3047:ros" "3048:rid-ms")

working_count=0
for port_info in "${ports[@]}"; do
    IFS=':' read -r port service <<< "$port_info"
    printf "%-6s %-25s " "$port" "$service"
    
    if timeout 1 bash -c "</dev/tcp/localhost/$port" 2>/dev/null; then
        echo -e "${GREEN}✓ Port Open${NC}"
        ((working_count++))
    else
        echo -e "${RED}✗ Port Closed${NC}"
    fi
done

echo -e "\n${GREEN}Total services listening: $working_count/10${NC}"

# Check logs for any errors
echo -e "\n${YELLOW}Checking for errors in newly started services:${NC}"
pm2 logs --lines 3 --nostream | grep -i "error\|listening" || true

EOF

echo -e "\n${GREEN}Service startup complete!${NC}"