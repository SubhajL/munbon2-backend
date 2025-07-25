#!/bin/bash

# Debug all services to find out why they're not responding
# Usage: ./debug-services-fixed-ec2.sh

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

echo -e "${BLUE}Debugging services on EC2...${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
# Don't use set -e here as we want to continue even if commands fail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

# Check actual listening ports using ss
echo -e "${BLUE}Checking actual listening ports...${NC}"
sudo ss -tlnp | grep -E ":(300[1-6]|301[1-4])" || echo "No services listening on expected ports"

# Check all Node.js processes
echo -e "\n${BLUE}All Node.js processes listening on ports:${NC}"
sudo ss -tlnp | grep node

# Test ROS service specifically
echo -e "\n${BLUE}Testing ROS service on port 3012...${NC}"
# First check if port is open
if sudo ss -tlnp | grep -q ":3012"; then
    echo "Port 3012 is listening"
    curl -v http://localhost:3012/health 2>&1 | head -20
else
    echo "Port 3012 is NOT listening"
fi

# Check PM2 process details
echo -e "\n${BLUE}PM2 process details:${NC}"
pm2 list

# Check if services are actually running
echo -e "\n${BLUE}Checking if Node.js processes are running:${NC}"
ps aux | grep -E "node|tsx|ts-node" | grep -v grep | head -10

# Fix flow-monitoring service
echo -e "\n${BLUE}Fixing flow-monitoring service...${NC}"
cd services/flow-monitoring
cat > run.sh << 'WRAPPER'
#!/bin/bash
cd /home/ubuntu/munbon2-backend/services/flow-monitoring
source venv/bin/activate
python src/main.py
WRAPPER
chmod +x run.sh
cd ../..

pm2 delete flow-monitoring || true
pm2 start services/flow-monitoring/run.sh --name flow-monitoring

# Check if services are crashing immediately
echo -e "\n${BLUE}Checking service status after 5 seconds...${NC}"
sleep 5
pm2 status

# Let's check the actual command PM2 is running for ROS
echo -e "\n${BLUE}PM2 process info for ROS:${NC}"
pm2 describe ros | grep -E "script|exec mode|interpreter"

# Try to start ROS manually to see what happens
echo -e "\n${BLUE}Testing ROS service manually...${NC}"
cd services/ros
timeout 5 npm run dev || echo "Manual start interrupted after 5 seconds"
cd ../..

# Check environment variables
echo -e "\n${BLUE}Checking HOST environment variable:${NC}"
pm2 env ros | grep -E "HOST|PORT"

# Final port check
echo -e "\n${BLUE}Final port check:${NC}"
for port in 3001 3002 3003 3004 3005 3006 3011 3012 3013 3014; do
    printf "Port %s: " "$port"
    if timeout 1 bash -c "</dev/tcp/localhost/$port" 2>/dev/null; then
        echo -e "${GREEN}✓ Port open${NC}"
    else
        echo -e "${RED}✗ Port closed${NC}"
    fi
done

# Get recent logs
echo -e "\n${YELLOW}Recent PM2 logs for all services:${NC}"
pm2 logs --lines 2 --nostream
EOF

echo -e "\n${GREEN}Debug complete!${NC}"