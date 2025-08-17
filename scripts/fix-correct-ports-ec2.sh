#!/bin/bash

# Fix PM2 configuration with CORRECT ports from service code
# Usage: ./fix-correct-ports-ec2.sh

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

echo -e "${BLUE}Fixing PM2 configuration with correct ports...${NC}"

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

# Create PM2 ecosystem file with CORRECT ports
echo -e "${BLUE}Creating PM2 ecosystem file with correct ports...${NC}"
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
        PORT: '3003',  // Correct port per user
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
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3002',  // Override default 3001
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
        PORT: '3005',  // Correct default port
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
        PORT: '3006',  // Correct default port
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
        PORT: '3008',  // Correct default port
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
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3007',  // Correct port per user
        HOST: '0.0.0.0',
        DATABASE_URL: 'postgresql://postgres:postgres123@localhost:5434/gis_db',
        REDIS_URL: 'redis://localhost:6379'
      }
    },
    {
      name: 'ros',
      cwd: './services/ros',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3047',  // Correct default port
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
        PORT: '3048',  // Correct default port
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
        PORT: '3010',  // Correct default port
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

# Start all services
echo -e "${BLUE}Starting all services with correct ports...${NC}"
pm2 start ecosystem.config.js

# Save PM2 config
pm2 save

# Wait for services
echo -e "${BLUE}Waiting for services to start...${NC}"
sleep 10

# Check status
echo -e "\n${GREEN}Service status:${NC}"
pm2 status

# Check listening ports
echo -e "\n${BLUE}Services listening on ports:${NC}"
sudo ss -tlnp | grep -E "node|python" | grep -E ":(300[2-8]|301[0-4]|304[7-8])" | awk '{print $4}' | sort

# Test all endpoints with CORRECT ports
echo -e "\n${BLUE}Testing service endpoints:${NC}"
echo -e "${YELLOW}Service                   Port    Status${NC}"
echo -e "${YELLOW}------------------------  ----    ------${NC}"

# Test each service on its CORRECT port
services=(
    "sensor-data:3003"
    "auth:3002"
    "gis:3007"
    "moisture-monitoring:3005"
    "weather-monitoring:3006"
    "water-level-monitoring:3008"
    "awd-control:3010"
    "flow-monitoring:3014"
    "ros:3047"
    "rid-ms:3048"
)

for service_info in "${services[@]}"; do
    IFS=':' read -r service port <<< "$service_info"
    printf "%-25s %-7s " "$service" "$port"
    
    if response=$(curl -s -m 2 "http://localhost:$port/health" 2>/dev/null); then
        echo -e "${GREEN}✓ Working${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi
done

echo -e "\n${YELLOW}Summary of port assignments:${NC}"
echo "sensor-data:             3003"
echo "auth:                    3002 (overriding default 3001)"
echo "gis:                     3007"
echo "moisture-monitoring:     3005"
echo "weather-monitoring:      3006"
echo "water-level-monitoring:  3008"
echo "awd-control:             3010"
echo "flow-monitoring:         3014"
echo "ros:                     3047"
echo "rid-ms:                  3048"

# Check for any port conflicts
echo -e "\n${BLUE}Checking for port conflicts...${NC}"
sudo ss -tlnp | grep -E ":(3002|3003|3005|3006|3007|3008|3010|3014|3047|3048)" | grep -v node | grep -v python || echo "No port conflicts found"
EOF

echo -e "\n${GREEN}Port configuration fixed!${NC}"

# Update security group info
echo -e "\n${YELLOW}Note: Update your EC2 security group to allow these ports:${NC}"
echo "- 3002, 3003, 3005, 3006, 3007, 3008, 3010, 3014, 3047, 3048"
echo ""
echo "AWS CLI command:"
echo "aws ec2 authorize-security-group-ingress --group-id <YOUR-SG-ID> --protocol tcp --port 3002-3003 --cidr 0.0.0.0/0"
echo "aws ec2 authorize-security-group-ingress --group-id <YOUR-SG-ID> --protocol tcp --port 3005-3008 --cidr 0.0.0.0/0"
echo "aws ec2 authorize-security-group-ingress --group-id <YOUR-SG-ID> --protocol tcp --port 3010 --cidr 0.0.0.0/0"
echo "aws ec2 authorize-security-group-ingress --group-id <YOUR-SG-ID> --protocol tcp --port 3014 --cidr 0.0.0.0/0"
echo "aws ec2 authorize-security-group-ingress --group-id <YOUR-SG-ID> --protocol tcp --port 3047-3048 --cidr 0.0.0.0/0"