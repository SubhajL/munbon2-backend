#!/bin/bash

# Debug all services to find out why they're not responding
# Usage: ./debug-services-ec2.sh

set -e

# Configuration
EC2_IP="43.209.22.250"
SSH_KEY="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"
EC2_USER="ubuntu"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}Debugging services on EC2...${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

# Check actual listening ports
echo -e "${BLUE}Checking actual listening ports...${NC}"
sudo netstat -tlnp | grep -E ":(300[1-6]|301[1-4])" || echo "No services listening on expected ports"

# Check if services are binding to localhost instead of 0.0.0.0
echo -e "\n${BLUE}Checking service binding addresses...${NC}"
sudo netstat -tlnp | grep node | grep 127.0.0.1 || echo "No services binding to localhost only"

# Test ROS service specifically since it says it's running
echo -e "\n${BLUE}Testing ROS service on port 3012...${NC}"
curl -v http://localhost:3012/health 2>&1 | grep -E "(Connected|HTTP|{)"

# Check if PM2 is running services with correct environment
echo -e "\n${BLUE}PM2 environment check...${NC}"
pm2 env 6 | grep -E "(PORT|HOST)" | head -10

# Fix flow-monitoring to use simple Python HTTP server
echo -e "\n${BLUE}Fixing flow-monitoring service...${NC}"
cd services/flow-monitoring
# Update the run.sh to directly run Python
cat > run.sh << 'WRAPPER'
#!/bin/bash
cd /home/ubuntu/munbon2-backend/services/flow-monitoring
source venv/bin/activate
python src/main.py
WRAPPER
chmod +x run.sh
cd ../..

# Restart flow-monitoring
pm2 delete flow-monitoring || true
pm2 start services/flow-monitoring/run.sh --name flow-monitoring

# Let's check if services need to be built first
echo -e "\n${BLUE}Checking if services need building...${NC}"
for service in sensor-data auth gis; do
    if [ -d "services/$service/src" ] && [ ! -d "services/$service/dist" ]; then
        echo -e "${YELLOW}$service needs building...${NC}"
        cd "services/$service"
        npm run build || echo "Build failed for $service"
        cd ../..
    fi
done

# Check environment variables being used
echo -e "\n${BLUE}Checking environment variables for each service...${NC}"
for i in 0 1 2 3 4 5 6 7 8; do
    echo -e "\n${YELLOW}Service ID $i:${NC}"
    pm2 env $i | grep -E "(PORT|HOST|DATABASE|TIMESCALE)" | head -5
done

# Restart all services with correct environment
echo -e "\n${BLUE}Restarting services with --update-env flag...${NC}"
pm2 restart all --update-env

# Wait a bit
sleep 5

# Final test
echo -e "\n${BLUE}Final endpoint test:${NC}"
for port in 3001 3002 3003 3004 3005 3006 3011 3012 3013 3014; do
    printf "Port %s: " "$port"
    if timeout 2 bash -c "echo > /dev/tcp/localhost/$port" 2>/dev/null; then
        echo -e "${GREEN}✓ Port open${NC}"
        curl -s -m 1 "http://localhost:$port/health" 2>/dev/null | head -c 100 || echo " (no HTTP response)"
    else
        echo -e "${RED}✗ Port closed${NC}"
    fi
done

# Check PM2 logs for the most recent errors
echo -e "\n${YELLOW}Most recent errors from PM2 logs:${NC}"
pm2 logs --lines 3 --nostream 2>/dev/null | grep -i "error\|fatal\|failed" | tail -10
EOF

echo -e "\n${GREEN}Debug complete!${NC}"