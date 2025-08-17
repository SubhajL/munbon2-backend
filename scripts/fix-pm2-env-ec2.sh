#!/bin/bash

# Fix PM2 environment variables
# Usage: ./fix-pm2-env-ec2.sh

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

echo -e "${BLUE}Fixing PM2 environment variables on EC2...${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

# Stop all services
echo -e "${BLUE}Stopping all services...${NC}"
pm2 stop all
pm2 delete all

# Create a better PM2 ecosystem file that forces environment variables
echo -e "${BLUE}Creating new PM2 ecosystem file with forced environment variables...${NC}"
cat > ecosystem.config.js << 'EOFPM2'
module.exports = {
  apps: [
    {
      name: 'sensor-data',
      cwd: './services/sensor-data',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3001',
        HOST: '0.0.0.0',
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: '5433',
        REDIS_HOST: 'localhost',
        DATABASE_URL: 'postgresql://postgres:postgres123@localhost:5433/sensor_data'
      },
      max_restarts: 3
    },
    {
      name: 'auth',
      cwd: './services/auth',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3002',
        HOST: '0.0.0.0',
        DATABASE_URL: 'postgresql://postgres:postgres123@localhost:5434/auth_db',
        REDIS_URL: 'redis://localhost:6379',
        JWT_SECRET: 'dev-jwt-secret-change-in-production',
        SESSION_SECRET: 'dev-session-secret-change-in-production'
      },
      max_restarts: 3
    },
    {
      name: 'moisture-monitoring',
      cwd: './services/moisture-monitoring',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3003',
        HOST: '0.0.0.0',
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: '5433',
        TIMESCALE_DATABASE: 'sensor_data',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: 'postgres123',
        MQTT_BROKER_URL: 'mqtt://localhost:1883',
        REDIS_HOST: 'localhost'
      },
      max_restarts: 3
    },
    {
      name: 'weather-monitoring',
      cwd: './services/weather-monitoring',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3004',
        HOST: '0.0.0.0',
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: '5433',
        TIMESCALE_DATABASE: 'sensor_data',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: 'postgres123',
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: '5434',
        POSTGRES_DATABASE: 'weather_db',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres123',
        MQTT_BROKER_URL: 'mqtt://localhost:1883',
        REDIS_HOST: 'localhost'
      },
      max_restarts: 3
    },
    {
      name: 'water-level-monitoring',
      cwd: './services/water-level-monitoring',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3005',
        HOST: '0.0.0.0',
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: '5433',
        TIMESCALE_DATABASE: 'sensor_data',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: 'postgres123',
        MQTT_BROKER_URL: 'mqtt://localhost:1883',
        REDIS_HOST: 'localhost'
      },
      max_restarts: 3
    },
    {
      name: 'gis',
      cwd: './services/gis',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3006',
        HOST: '0.0.0.0',
        DATABASE_URL: 'postgresql://postgres:postgres123@localhost:5434/gis_db',
        REDIS_URL: 'redis://localhost:6379'
      },
      max_restarts: 3
    },
    {
      name: 'ros',
      cwd: './services/ros',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3012',
        HOST: '0.0.0.0',
        DATABASE_URL: 'postgresql://postgres:postgres123@localhost:5434/ros_db',
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: '5434',
        POSTGRES_DB: 'ros_db',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres123',
        REDIS_HOST: 'localhost'
      },
      max_restarts: 3
    },
    {
      name: 'rid-ms',
      cwd: './services/rid-ms',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3011',
        HOST: '0.0.0.0',
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: '5434',
        POSTGRES_DB: 'rid_db',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres123',
        REDIS_HOST: 'localhost',
        KAFKA_BROKERS: 'localhost:9092'
      },
      max_restarts: 3
    },
    {
      name: 'awd-control',
      cwd: './services/awd-control',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3013',
        HOST: '0.0.0.0',
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: '5434',
        POSTGRES_DB: 'awd_db',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres123',
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: '5433',
        TIMESCALE_DB: 'sensor_data',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: 'postgres123',
        REDIS_HOST: 'localhost'
      },
      max_restarts: 3
    },
    {
      name: 'flow-monitoring',
      cwd: './services/flow-monitoring',
      script: './run.sh',
      env: {
        PORT: '3014',
        HOST: '0.0.0.0'
      },
      max_restarts: 3
    }
  ]
}
EOFPM2

# Start all services with the new config
echo -e "${BLUE}Starting all services with new configuration...${NC}"
pm2 start ecosystem.config.js

# Save PM2 config
pm2 save

# Wait for services to start
echo -e "${BLUE}Waiting for services to stabilize...${NC}"
sleep 10

# Check status
echo -e "\n${GREEN}Service status:${NC}"
pm2 status

# Check listening ports
echo -e "\n${BLUE}Checking listening ports:${NC}"
sudo ss -tlnp | grep -E ":(300[1-6]|301[1-4])" | awk '{print $4}' | sort

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
        if echo "$response" | grep -q "status"; then
            echo "  Response: $response" | head -c 100
            echo
        fi
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi
done

# Show any recent errors
echo -e "\n${YELLOW}Recent errors (if any):${NC}"
pm2 logs --lines 2 --nostream | grep -i "error" | tail -5 || echo "No recent errors"
EOF

echo -e "\n${GREEN}PM2 environment fix complete!${NC}"