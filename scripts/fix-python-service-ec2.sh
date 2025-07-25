#!/bin/bash

# Fix Python flow-monitoring service with virtual environment
# Usage: ./fix-python-service-ec2.sh

set -e

# Configuration
EC2_IP="43.209.12.182"
SSH_KEY="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"
EC2_USER="ubuntu"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}Fixing Python flow-monitoring service with virtual environment...${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend/services/flow-monitoring

# Create virtual environment
echo -e "${BLUE}Creating Python virtual environment...${NC}"
python3 -m venv venv

# Activate and install dependencies
echo -e "${BLUE}Installing Python dependencies...${NC}"
source venv/bin/activate
pip install structlog influxdb-client python-dotenv pandas numpy

# Create a wrapper script that uses the virtual environment
echo -e "${BLUE}Creating wrapper script...${NC}"
cat > run.sh << 'WRAPPER'
#!/bin/bash
cd /home/ubuntu/munbon2-backend/services/flow-monitoring
source venv/bin/activate
python src/main.py
WRAPPER
chmod +x run.sh

# Update PM2 to use the wrapper script
cd /home/ubuntu/munbon2-backend

# Update just the flow-monitoring entry in ecosystem config
echo -e "${BLUE}Updating PM2 configuration for flow-monitoring...${NC}"
pm2 delete flow-monitoring || true

# Start flow-monitoring with the wrapper script
pm2 start services/flow-monitoring/run.sh --name flow-monitoring --env PORT=3014 --env HOST=0.0.0.0

# Save PM2 config
pm2 save

echo -e "${GREEN}Python service fixed!${NC}"

# Check if it's running
sleep 5
pm2 status flow-monitoring

# Test the endpoint
echo -e "\n${BLUE}Testing flow-monitoring endpoint...${NC}"
if curl -s -m 2 "http://localhost:3014/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Flow monitoring service is working!${NC}"
    curl -s "http://localhost:3014/health" | python3 -m json.tool
else
    echo -e "${YELLOW}Flow monitoring service not responding yet${NC}"
    pm2 logs flow-monitoring --lines 20 --nostream
fi
EOF

echo -e "${GREEN}Python service configuration complete!${NC}"

# Now let's check all services status
echo -e "\n${BLUE}Checking all services status on EC2...${NC}"
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
# Show PM2 status
pm2 status

# Check listening ports
echo -e "\n${BLUE}Services listening on ports:${NC}"
sudo ss -tlnp | grep -E ":(300[1-6]|301[1-4])" | awk '{print $4 " - " $6}' || echo "Checking..."

# Test all endpoints
echo -e "\n${BLUE}Testing all service endpoints:${NC}"
for port in 3001 3002 3003 3004 3005 3006 3011 3012 3013 3014; do
    service_name=""
    case $port in
        3001) service_name="sensor-data" ;;
        3002) service_name="auth" ;;
        3003) service_name="moisture-monitoring" ;;
        3004) service_name="weather-monitoring" ;;
        3005) service_name="water-level-monitoring" ;;
        3006) service_name="gis" ;;
        3011) service_name="rid-ms" ;;
        3012) service_name="ros" ;;
        3013) service_name="awd-control" ;;
        3014) service_name="flow-monitoring" ;;
    esac
    
    echo -n "$service_name (port $port): "
    if curl -s -m 2 "http://localhost:$port/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Working${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi
done
EOF