#!/bin/bash

# Build TypeScript services that are missing dist/
# Usage: ./build-services-ec2.sh

set -e

# Configuration
EC2_IP="43.209.12.182"
SSH_KEY="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"
EC2_USER="ubuntu"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}Building TypeScript services on EC2...${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

# Build auth service
echo -e "${BLUE}Building auth service...${NC}"
cd services/auth
npm run build
cd ../..

# Build ros service
echo -e "${BLUE}Building ros service...${NC}"
cd services/ros
npm run build
cd ../..

# Also check other services that might need building
echo -e "${BLUE}Checking other services...${NC}"
for service in sensor-data gis awd-control rid-ms weather-monitoring; do
    if [ -f "services/$service/tsconfig.json" ] && [ ! -d "services/$service/dist" ]; then
        echo -e "${YELLOW}Building $service...${NC}"
        cd "services/$service"
        npm run build || echo "Build failed for $service"
        cd ../..
    fi
done

# Restart all services to pick up builds
echo -e "${BLUE}Restarting all services...${NC}"
pm2 restart all

sleep 10

# Check all ports
echo -e "\n${GREEN}Service port status after builds:${NC}"
echo -e "${YELLOW}Port   Service                    Status${NC}"
echo -e "${YELLOW}----   ----------------------     ------${NC}"

ports=("3002:auth" "3003:sensor-data" "3005:moisture-monitoring" "3006:weather-monitoring" 
       "3007:gis" "3008:water-level-monitoring" "3010:awd-control" "3014:flow-monitoring" 
       "3047:ros" "3048:rid-ms")

for port_info in "${ports[@]}"; do
    IFS=':' read -r port service <<< "$port_info"
    printf "%-6s %-25s " "$port" "$service"
    
    if timeout 1 bash -c "</dev/tcp/localhost/$port" 2>/dev/null; then
        echo -e "${GREEN}✓ Port Open${NC}"
    else
        echo -e "${RED}✗ Port Closed${NC}"
    fi
done

# Show PM2 status
echo -e "\n${BLUE}PM2 Status:${NC}"
pm2 status

EOF

echo -e "\n${GREEN}Build complete!${NC}"