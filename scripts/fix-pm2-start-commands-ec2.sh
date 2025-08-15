#!/bin/bash

# Fix PM2 start commands to use correct entry points
# Usage: ./fix-pm2-start-commands-ec2.sh

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

echo -e "${BLUE}Fixing PM2 start commands on EC2...${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

# Stop and delete all services
echo -e "${BLUE}Stopping all services...${NC}"
pm2 stop all
pm2 delete all

# Create PM2 ecosystem file with CORRECT start commands
echo -e "${BLUE}Creating PM2 ecosystem file with correct start commands...${NC}"
cat > ecosystem.config.js << 'EOFPM2'
module.exports = {
  apps: [
    {
      name: 'sensor-data',
      cwd: './services/sensor-data',
      script: 'npx',
      args: 'ts-node src/cmd/server/main.ts',
      env: {
        NODE_ENV: 'production',
        PORT: '3003',
        HOST: '0.0.0.0',
        HEALTH_MONITOR_PORT: '3003',
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: '5433',
        REDIS_HOST: 'localhost',
        DATABASE_URL: 'postgresql://postgres:postgres123@localhost:5433/sensor_data'
      }
    },
    {
      name: 'auth',
      cwd: './services/auth',
      script: 'npx',
      args: 'ts-node src/index.ts',
      env: {
        NODE_ENV: 'production',
        PORT: '3002',
        HOST: '0.0.0.0',
        DATABASE_URL: 'postgresql://postgres:postgres123@localhost:5434/auth_db',
        REDIS_URL: 'redis://localhost:6379',
        JWT_SECRET: 'dev-jwt-secret-change-in-production',
        SESSION_SECRET: 'dev-session-secret-change-in-production',
        OAUTH_CALLBACK_URL: 'http://localhost:3002/auth/callback',
        THAI_DIGITAL_ID_CLIENT_ID: 'dummy',
        THAI_DIGITAL_ID_CLIENT_SECRET: 'dummy',
        THAI_DIGITAL_ID_AUTH_URL: 'dummy',
        THAI_DIGITAL_ID_TOKEN_URL: 'dummy', 
        THAI_DIGITAL_ID_USERINFO_URL: 'dummy',
        SMTP_HOST: 'smtp.gmail.com',
        SMTP_USER: 'dummy',
        SMTP_PASS: 'dummy',
        EMAIL_FROM: 'noreply@munbon.com'
      }
    },
    {
      name: 'moisture-monitoring',
      cwd: './services/moisture-monitoring',
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
      }
    },
    {
      name: 'weather-monitoring',
      cwd: './services/weather-monitoring',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3006',
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
      }
    },
    {
      name: 'water-level-monitoring',
      cwd: './services/water-level-monitoring',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3008',
        HOST: '0.0.0.0',
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: '5433',
        TIMESCALE_DATABASE: 'sensor_data',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: 'postgres123',
        MQTT_BROKER_URL: 'mqtt://localhost:1883',
        REDIS_HOST: 'localhost'
      }
    },
    {
      name: 'gis',
      cwd: './services/gis',
      script: 'npx',
      args: 'ts-node src/index.ts',
      env: {
        NODE_ENV: 'production',
        PORT: '3007',
        HOST: '0.0.0.0',
        DATABASE_URL: 'postgresql://postgres:postgres123@localhost:5434/gis_db',
        REDIS_URL: 'redis://localhost:6379'
      }
    },
    {
      name: 'ros',
      cwd: './services/ros',
      script: 'npx',
      args: 'tsx src/index.ts',
      env: {
        NODE_ENV: 'production',
        PORT: '3047',
        HOST: '0.0.0.0',
        DATABASE_URL: 'postgresql://postgres:postgres123@localhost:5434/ros_db',
        DB_HOST: 'localhost',
        DB_PORT: '5434',
        DB_NAME: 'ros_db',
        DB_USER: 'postgres',
        DB_PASSWORD: 'postgres123',
        REDIS_HOST: 'localhost',
        REDIS_PORT: '6379'
      }
    },
    {
      name: 'rid-ms',
      cwd: './services/rid-ms',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3048',
        HOST: '0.0.0.0',
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: '5434',
        POSTGRES_DB: 'rid_db',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres123',
        REDIS_HOST: 'localhost',
        KAFKA_BROKERS: 'localhost:9092'
      }
    },
    {
      name: 'awd-control',
      cwd: './services/awd-control',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3010',
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
        REDIS_HOST: 'localhost',
        REDIS_PORT: '6379'
      }
    },
    {
      name: 'flow-monitoring',
      cwd: './services/flow-monitoring',
      script: './run.sh',
      env: {
        PORT: '3014',
        HOST: '0.0.0.0'
      }
    }
  ]
}
EOFPM2

# Install tsx globally if not installed
echo -e "${BLUE}Installing tsx globally...${NC}"
npm install -g tsx ts-node

# Start all services
echo -e "${BLUE}Starting all services with correct commands...${NC}"
pm2 start ecosystem.config.js

# Save PM2 config
pm2 save

# Wait for services
echo -e "${BLUE}Waiting for services to start...${NC}"
sleep 15

# Check status
echo -e "\n${GREEN}Service status:${NC}"
pm2 status

# Check all ports
echo -e "\n${GREEN}Service port status:${NC}"
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

# Check for TypeScript/Node errors
echo -e "\n${YELLOW}Recent errors (if any):${NC}"
pm2 logs --lines 3 --nostream | grep -i "error\|cannot find" | tail -10 || echo "No recent errors"

EOF

echo -e "\n${GREEN}PM2 start commands fixed!${NC}"