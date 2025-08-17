#!/bin/bash

# Check what environment variables each service expects
# Usage: ./check-service-configs-ec2.sh

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

echo -e "${BLUE}Checking service configurations on EC2...${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

# Function to check config requirements
check_service_config() {
    local service=$1
    local config_file=""
    
    echo -e "\n${BLUE}=== $service ===${NC}"
    
    # Find config file
    if [ -f "services/$service/src/config/index.ts" ]; then
        config_file="services/$service/src/config/index.ts"
    elif [ -f "services/$service/src/config/database.ts" ]; then
        config_file="services/$service/src/config/database.ts"
    elif [ -f "services/$service/src/config.ts" ]; then
        config_file="services/$service/src/config.ts"
    fi
    
    if [ -n "$config_file" ]; then
        echo "Config file: $config_file"
        echo "Required environment variables:"
        grep -E "(process\.env\.|getEnv|required|DATABASE_URL|TIMESCALE_|POSTGRES_|REDIS_|INFLUX_)" "$config_file" | grep -v "//" | head -20
    else
        echo "No config file found"
    fi
    
    # Check if .env exists
    if [ -f "services/$service/.env" ]; then
        echo -e "${GREEN}.env file exists${NC}"
        echo "Current .env contents:"
        head -10 "services/$service/.env"
    else
        echo -e "${RED}.env file missing${NC}"
    fi
}

# Check each service
services=("sensor-data" "auth" "moisture-monitoring" "weather-monitoring" "water-level-monitoring" "gis" "rid-ms" "awd-control")

for service in "${services[@]}"; do
    check_service_config "$service"
done

# Special check for flow-monitoring Python service
echo -e "\n${BLUE}=== flow-monitoring (Python) ===${NC}"
if [ -f "services/flow-monitoring/src/main.py" ]; then
    echo "Checking Python imports:"
    head -20 "services/flow-monitoring/src/main.py"
fi

# Check PM2 logs for specific errors
echo -e "\n${YELLOW}Recent error messages:${NC}"
pm2 logs --lines 5 --nostream 2>/dev/null | grep -E "(Error:|required|missing|failed)" | tail -20
EOF