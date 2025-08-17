#!/bin/bash

# Fix service dependencies and databases
# Usage: ./fix-service-dependencies-ec2.sh

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

echo -e "${BLUE}Fixing service dependencies on EC2...${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

# Fix missing jsonwebtoken for weather-monitoring
echo -e "${YELLOW}Installing jsonwebtoken for weather-monitoring...${NC}"
cd services/weather-monitoring
npm install jsonwebtoken --save
cd ../..

# Fix database connections
echo -e "${BLUE}Creating missing databases...${NC}"
docker exec -it munbon-postgres psql -U postgres -c "CREATE DATABASE ros_db;" 2>/dev/null || true
docker exec -it munbon-postgres psql -U postgres -c "CREATE DATABASE awd_db;" 2>/dev/null || true

# Check if MQTT broker is needed (optional for now)
echo -e "${BLUE}Checking for MQTT container...${NC}"
if ! docker ps | grep -q mqtt; then
    echo -e "${YELLOW}No MQTT broker running - moisture and water-level monitoring will have errors but still work${NC}"
fi

# Fix flow-monitoring Python service
echo -e "${BLUE}Checking flow-monitoring service...${NC}"
if [ -f services/flow-monitoring/src/main.py ]; then
    echo "Flow monitoring service file exists"
else
    echo -e "${RED}Flow monitoring main.py missing!${NC}"
fi

# Restart affected services
echo -e "${BLUE}Restarting services...${NC}"
pm2 restart weather-monitoring ros awd-control auth sensor-data gis rid-ms

sleep 10

# Check ports
echo -e "\n${GREEN}Checking service ports:${NC}"
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
        # Try health check
        if response=$(curl -s -m 1 "http://localhost:$port/health" 2>/dev/null); then
            echo "       Health: OK"
        else
            echo "       Health: Port open but no HTTP response"
        fi
    else
        echo -e "${RED}✗ Port Closed${NC}"
    fi
done

# Show any recent errors
echo -e "\n${YELLOW}Recent errors (last 2 lines per service):${NC}"
pm2 logs --lines 2 --nostream 2>&1 | grep -i "error" | head -10 || echo "No recent errors"
EOF

echo -e "\n${GREEN}Dependency fix complete!${NC}"