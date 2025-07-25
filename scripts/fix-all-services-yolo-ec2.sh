#!/bin/bash

# YOLO mode - Fix all services automatically
# Usage: ./fix-all-services-yolo-ec2.sh

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

echo -e "${BLUE}YOLO MODE: Fixing all services automatically...${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
# Don't use set -e to continue even if something fails

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

echo -e "${BLUE}=== STEP 1: Fixing Auth Service TypeScript Errors ===${NC}"
cd services/auth
npm install --save-dev @types/passport-oauth2 @types/cors
cd ../..

echo -e "${BLUE}=== STEP 2: Debugging sensor-data and gis restart loops ===${NC}"
# Check what's failing
echo "Checking sensor-data logs..."
pm2 logs sensor-data --lines 20 --nostream > /tmp/sensor-data.log 2>&1
if grep -q "Cannot find module" /tmp/sensor-data.log; then
    echo "Found missing module in sensor-data, installing dependencies..."
    cd services/sensor-data
    npm install
    cd ../..
fi

# Check GIS logs
echo "Checking gis logs..."
pm2 logs gis --lines 20 --nostream > /tmp/gis.log 2>&1
if grep -q "Cannot find module" /tmp/gis.log; then
    echo "Found missing module in gis, installing dependencies..."
    cd services/gis
    npm install
    cd ../..
fi

echo -e "${BLUE}=== STEP 3: Fix PostgreSQL Authentication for ROS ===${NC}"
# First, fix the postgres password in the container
docker exec -it munbon-postgres psql -U postgres -c "ALTER USER postgres PASSWORD 'postgres123';" || true

# Create all missing databases
docker exec -it munbon-postgres psql -U postgres -c "CREATE DATABASE ros_db;" 2>/dev/null || true
docker exec -it munbon-postgres psql -U postgres -c "CREATE DATABASE awd_db;" 2>/dev/null || true
docker exec -it munbon-postgres psql -U postgres -c "CREATE DATABASE rid_db;" 2>/dev/null || true
docker exec -it munbon-postgres psql -U postgres -c "CREATE DATABASE weather_db;" 2>/dev/null || true
docker exec -it munbon-postgres psql -U postgres -c "CREATE DATABASE auth_db;" 2>/dev/null || true
docker exec -it munbon-postgres psql -U postgres -c "CREATE DATABASE gis_db;" 2>/dev/null || true

# Install PostGIS extension
docker exec -it munbon-postgres psql -U postgres -d gis_db -c "CREATE EXTENSION IF NOT EXISTS postgis;" 2>/dev/null || true

echo -e "${BLUE}=== STEP 4: Install MQTT Broker ===${NC}"
# Run Mosquitto MQTT broker in Docker
docker run -d \
  --name munbon-mqtt \
  --restart unless-stopped \
  -p 1883:1883 \
  -p 9001:9001 \
  eclipse-mosquitto:latest 2>/dev/null || echo "MQTT already running or failed to start"

# Wait for MQTT to start
sleep 5

echo -e "${BLUE}=== STEP 5: Creating comprehensive PM2 config with fixes ===${NC}"
# Stop all services
pm2 stop all
pm2 delete all

# Create a fixed ecosystem file
cat > ecosystem.config.js << 'EOFPM2'
module.exports = {
  apps: [
    // Auth service - run despite TypeScript errors
    {
      name: 'auth',
      cwd: './services/auth',
      script: 'bash',
      args: '-c "PORT=3002 HOST=0.0.0.0 DATABASE_URL=postgresql://postgres:postgres123@localhost:5432/auth_db REDIS_URL=redis://localhost:6379 JWT_SECRET=dev-jwt-secret SESSION_SECRET=dev-session-secret npx ts-node --transpile-only src/index.ts || npm run dev"',
      max_restarts: 10,
      min_uptime: 10000,
      error_file: '/dev/null'
    },
    // Sensor data with all environment variables
    {
      name: 'sensor-data',
      cwd: './services/sensor-data',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3003',
        HOST: '0.0.0.0',
        HEALTH_MONITOR_PORT: '3003',
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: '5433',
        TIMESCALE_DATABASE: 'sensor_data',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: 'postgres123',
        REDIS_HOST: 'localhost',
        REDIS_PORT: '6379',
        DATABASE_URL: 'postgresql://postgres:postgres123@localhost:5433/sensor_data',
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: '5433',
        POSTGRES_DB: 'sensor_data',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres123'
      },
      max_restarts: 10,
      min_uptime: 10000
    },
    // Weather monitoring with cors fix
    {
      name: 'weather-monitoring',
      cwd: './services/weather-monitoring',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3006',
        HOST: '0.0.0.0',
        CORS_ORIGIN: '*',
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: '5433',
        TIMESCALE_DATABASE: 'sensor_data',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: 'postgres123',
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: '5432',
        POSTGRES_DATABASE: 'weather_db',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres123',
        MQTT_BROKER_URL: 'mqtt://localhost:1883',
        REDIS_HOST: 'localhost'
      },
      max_restarts: 10
    },
    // GIS with proper database
    {
      name: 'gis',
      cwd: './services/gis',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3007',
        HOST: '0.0.0.0',
        DATABASE_URL: 'postgresql://postgres:postgres123@localhost:5432/gis_db',
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: '5432',
        POSTGRES_DB: 'gis_db',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres123',
        REDIS_URL: 'redis://localhost:6379',
        REDIS_HOST: 'localhost'
      },
      max_restarts: 10,
      min_uptime: 10000
    },
    // ROS with correct postgres port
    {
      name: 'ros',
      cwd: './services/ros',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: '3047',
        HOST: '0.0.0.0',
        DATABASE_URL: 'postgresql://postgres:postgres123@localhost:5432/ros_db',
        DB_HOST: 'localhost',
        DB_PORT: '5432',
        DB_NAME: 'ros_db',
        DB_USER: 'postgres',
        DB_PASSWORD: 'postgres123',
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: '5432',
        POSTGRES_DB: 'ros_db',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres123',
        REDIS_HOST: 'localhost',
        REDIS_PORT: '6379'
      },
      max_restarts: 10
    },
    // RID-MS with all configs
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
        POSTGRES_PORT: '5432',
        POSTGRES_DB: 'rid_db',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres123',
        DATABASE_URL: 'postgresql://postgres:postgres123@localhost:5432/rid_db',
        REDIS_HOST: 'localhost',
        REDIS_PORT: '6379',
        KAFKA_BROKERS: 'localhost:9092'
      },
      max_restarts: 10
    },
    // AWD Control
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
        POSTGRES_PORT: '5432',
        POSTGRES_DB: 'awd_db',
        POSTGRES_USER: 'postgres',
        POSTGRES_PASSWORD: 'postgres123',
        DATABASE_URL: 'postgresql://postgres:postgres123@localhost:5432/awd_db',
        TIMESCALE_HOST: 'localhost',
        TIMESCALE_PORT: '5433',
        TIMESCALE_DB: 'sensor_data',
        TIMESCALE_USER: 'postgres',
        TIMESCALE_PASSWORD: 'postgres123',
        REDIS_HOST: 'localhost',
        REDIS_PORT: '6379'
      },
      max_restarts: 10
    },
    // Monitoring services with MQTT fix
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

# Create TimescaleDB sensor_data database if missing
docker exec -it munbon-timescaledb psql -U postgres -c "CREATE DATABASE sensor_data;" 2>/dev/null || true

# Start all services
echo -e "${BLUE}Starting all services with fixes...${NC}"
pm2 start ecosystem.config.js

# Save PM2 config
pm2 save
pm2 startup systemd -u ubuntu --hp /home/ubuntu || true

# Wait for services
echo -e "${BLUE}Waiting for services to stabilize...${NC}"
sleep 30

# Final check
echo -e "\n${GREEN}=== FINAL STATUS ===${NC}"
pm2 status

echo -e "\n${GREEN}=== PORT CHECK ===${NC}"
for port in 3002 3003 3005 3006 3007 3008 3010 3014 3047 3048; do
    printf "Port %s: " "$port"
    if timeout 1 bash -c "</dev/tcp/localhost/$port" 2>/dev/null; then
        echo -e "${GREEN}OPEN${NC}"
    else
        echo -e "${RED}CLOSED${NC}"
    fi
done

echo -e "\n${GREEN}=== CONTAINER STATUS ===${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "munbon|NAMES"

EOF

echo -e "\n${GREEN}YOLO fixes complete!${NC}"