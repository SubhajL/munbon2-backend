#!/bin/bash

# Final diagnostic and fix for non-working services
# Usage: ./final-diagnostic-fix-ec2.sh

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

echo -e "${BLUE}Running final diagnostics and fixes...${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
# Don't use set -e to continue diagnostics

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

echo -e "${BLUE}=== Checking each non-working service ===${NC}"

# Check sensor-data (3003)
echo -e "\n${YELLOW}1. sensor-data (3003):${NC}"
pm2 logs sensor-data --lines 15 --nostream | grep -E "error|Error|failed|listen|port" || echo "No relevant logs"

# Check auth (3002)
echo -e "\n${YELLOW}2. auth (3002):${NC}"
pm2 logs auth --lines 15 --nostream | grep -E "error|Error|failed|listen|port" || echo "No relevant logs"

# Check weather-monitoring (3006)
echo -e "\n${YELLOW}3. weather-monitoring (3006):${NC}"
pm2 logs weather-monitoring --lines 15 --nostream | grep -E "error|Error|failed|listen|port" || echo "No relevant logs"

# Check gis (3007)
echo -e "\n${YELLOW}4. gis (3007):${NC}"
pm2 logs gis --lines 15 --nostream | grep -E "error|Error|failed|listen|port" || echo "No relevant logs"

# Check ros (3047)
echo -e "\n${YELLOW}5. ros (3047):${NC}"
pm2 logs ros --lines 15 --nostream | grep -E "error|Error|failed|listen|port" || echo "No relevant logs"

# Check rid-ms (3048)
echo -e "\n${YELLOW}6. rid-ms (3048):${NC}"
pm2 logs rid-ms --lines 15 --nostream | grep -E "error|Error|failed|listen|port" || echo "No relevant logs"

# Check awd-control (3010)
echo -e "\n${YELLOW}7. awd-control (3010):${NC}"
pm2 logs awd-control --lines 15 --nostream | grep -E "error|Error|failed|listen|port" || echo "No relevant logs"

echo -e "\n${BLUE}=== Applying targeted fixes ===${NC}"

# Fix 1: Install missing dependencies for sensor-data
echo -e "${YELLOW}Installing dependencies for sensor-data...${NC}"
cd services/sensor-data
npm install aws-sdk @types/aws-lambda sqs-consumer @aws-sdk/client-sqs
cd ../..

# Fix 2: Run auth with transpile-only flag
echo -e "${YELLOW}Restarting auth with transpile-only...${NC}"
pm2 delete auth
pm2 start services/auth/src/index.ts --name auth --interpreter "npx ts-node --transpile-only" -- --port 3002

# Fix 3: Create proper .env files
echo -e "${YELLOW}Creating .env files for services...${NC}"
cat > services/weather-monitoring/.env << 'ENVEOF'
NODE_ENV=production
PORT=3006
HOST=0.0.0.0
CORS_ORIGIN=*
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DATABASE=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres123
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=weather_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123
MQTT_BROKER_URL=mqtt://localhost:1883
REDIS_HOST=localhost
ENVEOF

cat > services/gis/.env << 'ENVEOF'
NODE_ENV=production
PORT=3007
HOST=0.0.0.0
DATABASE_URL=postgresql://postgres:postgres123@localhost:5432/gis_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=gis_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123
REDIS_URL=redis://localhost:6379
REDIS_HOST=localhost
ENVEOF

cat > services/ros/.env << 'ENVEOF'
NODE_ENV=production
PORT=3047
HOST=0.0.0.0
DATABASE_URL=postgresql://postgres:postgres123@localhost:5432/ros_db
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ros_db
DB_USER=postgres
DB_PASSWORD=postgres123
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ros_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123
REDIS_HOST=localhost
REDIS_PORT=6379
ENVEOF

# Fix 4: Restart services with pm2 and proper environment
echo -e "${YELLOW}Restarting services with .env files...${NC}"
pm2 restart weather-monitoring gis ros rid-ms awd-control sensor-data

# Wait for services
sleep 20

echo -e "\n${GREEN}=== FINAL CHECK ===${NC}"
echo -e "${YELLOW}Service              Port    Status${NC}"
echo -e "${YELLOW}------------------   ----    ------${NC}"

services=(
    "auth:3002"
    "sensor-data:3003"
    "moisture-monitoring:3005"
    "weather-monitoring:3006"
    "gis:3007"
    "water-level-monitoring:3008"
    "awd-control:3010"
    "flow-monitoring:3014"
    "ros:3047"
    "rid-ms:3048"
)

working=0
total=10

for service_info in "${services[@]}"; do
    IFS=':' read -r service port <<< "$service_info"
    printf "%-20s %-7s " "$service" "$port"
    
    if timeout 1 bash -c "</dev/tcp/localhost/$port" 2>/dev/null; then
        echo -e "${GREEN}✓ WORKING${NC}"
        ((working++))
    else
        echo -e "${RED}✗ NOT WORKING${NC}"
    fi
done

echo -e "\n${GREEN}Total working: $working/$total${NC}"

# Show MQTT status
echo -e "\n${BLUE}MQTT Broker Status:${NC}"
docker ps | grep mqtt && echo -e "${GREEN}✓ MQTT running${NC}" || echo -e "${RED}✗ MQTT not running${NC}"

# Show database status
echo -e "\n${BLUE}Database Status:${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "postgres|redis|influx|mongo|timescale"

EOF

echo -e "\n${GREEN}Final diagnostics complete!${NC}"