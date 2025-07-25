#!/bin/bash

# Restart all services on EC2
# Usage: ./restart-all-services-ec2.sh

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

echo -e "${BLUE}Restarting all services on EC2...${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

# First, ensure databases are running
echo -e "${BLUE}Checking Docker databases...${NC}"
docker-compose up -d postgres timescaledb redis influxdb mongodb
sleep 10

# Restart all Node.js services using ecosystem config
echo -e "${BLUE}Restarting all Node.js services...${NC}"
pm2 restart ecosystem.config.js || pm2 start ecosystem.config.js

# Fix flow-monitoring Python service
echo -e "${BLUE}Fixing flow-monitoring Python service...${NC}"
cd services/flow-monitoring

# Check what main.py is trying to use
if grep -q "fastapi" src/main.py; then
    echo -e "${YELLOW}Installing FastAPI dependencies...${NC}"
    source venv/bin/activate
    pip install fastapi uvicorn
    
    # Update wrapper to use uvicorn
    cat > run.sh << 'WRAPPER'
#!/bin/bash
cd /home/ubuntu/munbon2-backend/services/flow-monitoring
source venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 3014
WRAPPER
    chmod +x run.sh
else
    # Keep the simple HTTP server version
    echo -e "${YELLOW}Using simple HTTP server...${NC}"
fi

cd /home/ubuntu/munbon2-backend

# Restart flow-monitoring
pm2 delete flow-monitoring || true
pm2 start services/flow-monitoring/run.sh --name flow-monitoring

# Save PM2
pm2 save

# Wait for services to stabilize
echo -e "${BLUE}Waiting for services to start...${NC}"
sleep 15

# Show status
echo -e "${GREEN}All services restarted!${NC}"
pm2 status

# Check listening ports
echo -e "\n${BLUE}Services listening on ports:${NC}"
sudo ss -tlnp | grep -E ":(300[1-6]|301[1-4])" | while read line; do
    port=$(echo $line | grep -oE ":[0-9]+" | tail -1 | tr -d ':')
    process=$(echo $line | awk -F'"' '{print $2}' | head -1)
    echo "Port $port: $process"
done

# Test all endpoints
echo -e "\n${BLUE}Testing service endpoints:${NC}"
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
    
    printf "%-25s: " "$service_name (port $port)"
    if response=$(curl -s -m 2 "http://localhost:$port/health" 2>/dev/null); then
        echo -e "${GREEN}✓ Working${NC}"
        # Show response if it's JSON
        if echo "$response" | python3 -m json.tool >/dev/null 2>&1; then
            echo "  Response: $(echo $response | jq -c . 2>/dev/null || echo $response)"
        fi
    else
        echo -e "${RED}✗ Not responding${NC}"
        # Check PM2 logs for this service
        pm2 logs "$service_name" --lines 3 --nostream 2>/dev/null | grep -i error | head -1 | sed 's/^/  Error: /'
    fi
done

# Summary
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}Service Summary:${NC}"
echo -e "${BLUE}========================================${NC}"

# Count working services
working=$(curl -s -m 2 http://localhost:3001/health >/dev/null 2>&1 && echo 1 || echo 0)
for port in 3002 3003 3004 3005 3006 3011 3012 3013 3014; do
    if curl -s -m 2 "http://localhost:$port/health" >/dev/null 2>&1; then
        working=$((working + 1))
    fi
done

echo -e "Working services: ${GREEN}$working/10${NC}"
echo -e "\nDocker containers:"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "(postgres|timescale|redis|influx|mongo)" | head -6

echo -e "\n${YELLOW}Note: If services are not accessible externally, check:${NC}"
echo "1. EC2 security group allows ports 3001-3014"
echo "2. Services are binding to 0.0.0.0 (check .env files)"
echo "3. No firewall blocking the ports"
EOF

echo -e "\n${GREEN}Restart complete!${NC}"

# Test from local machine
echo -e "\n${BLUE}Testing external access from local machine...${NC}"
accessible=0
for port in 3001 3002 3003 3004 3005 3006 3011 3012 3013 3014; do
    if curl -s -m 2 "http://$EC2_IP:$port/health" >/dev/null 2>&1; then
        accessible=$((accessible + 1))
    fi
done

if [ $accessible -gt 0 ]; then
    echo -e "${GREEN}$accessible/10 services are externally accessible${NC}"
else
    echo -e "${RED}No services are externally accessible${NC}"
    echo -e "${YELLOW}This likely means the EC2 security group needs to be updated${NC}"
    echo ""
    echo "To check security group:"
    echo "aws ec2 describe-instances --instance-ids <instance-id> --query 'Reservations[0].Instances[0].SecurityGroups'"
    echo ""
    echo "To add inbound rules:"
    echo "aws ec2 authorize-security-group-ingress --group-id <sg-id> --protocol tcp --port 3001-3014 --cidr 0.0.0.0/0"
fi