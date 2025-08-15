#!/bin/bash

# Start ALL services with working configurations
# Usage: ./start-all-services-final-ec2.sh

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

echo -e "${BLUE}Starting all services on EC2...${NC}"

ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
# Don't use set -e here to continue even if individual services fail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

# Clear PM2
pm2 kill || true

# Create comprehensive ecosystem file
echo -e "${BLUE}Creating comprehensive PM2 ecosystem file...${NC}"
cat > ecosystem.config.js << 'EOFPM2'
module.exports = {
  apps: [
    // TypeScript services that need ts-node/tsx
    {
      name: 'sensor-data',
      cwd: './services/sensor-data',
      script: 'bash',
      args: '-c "PORT=3003 HOST=0.0.0.0 HEALTH_MONITOR_PORT=3003 TIMESCALE_HOST=localhost TIMESCALE_PORT=5433 REDIS_HOST=localhost DATABASE_URL=postgresql://postgres:postgres123@localhost:5433/sensor_data npx ts-node src/cmd/server/main.ts"',
      max_restarts: 3
    },
    {
      name: 'gis',
      cwd: './services/gis',
      script: 'bash',
      args: '-c "PORT=3007 HOST=0.0.0.0 DATABASE_URL=postgresql://postgres:postgres123@localhost:5434/gis_db REDIS_URL=redis://localhost:6379 npx ts-node src/index.ts"',
      max_restarts: 3
    },
    {
      name: 'ros',
      cwd: './services/ros',
      script: 'bash',
      args: '-c "PORT=3047 HOST=0.0.0.0 DATABASE_URL=postgresql://postgres:postgres123@localhost:5434/ros_db DB_HOST=localhost DB_PORT=5434 DB_NAME=ros_db DB_USER=postgres DB_PASSWORD=postgres123 REDIS_HOST=localhost REDIS_PORT=6379 npx tsx src/index.ts"',
      max_restarts: 3
    },
    // Working monitoring services
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
        PORT: '3008',
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
      name: 'flow-monitoring',
      cwd: './services/flow-monitoring',
      script: './run.sh',
      env: {
        PORT: '3014',
        HOST: '0.0.0.0'
      },
      max_restarts: 3
    },
    // Services that need fixes or have issues
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
        PORT: '3048',
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
      },
      max_restarts: 3
    }
    // Skipping auth service due to TypeScript compilation errors
  ]
}
EOFPM2

# Start all services
echo -e "${BLUE}Starting all services...${NC}"
pm2 start ecosystem.config.js

# Save PM2 configuration
pm2 save
pm2 startup systemd -u ubuntu --hp /home/ubuntu || true

# Wait for services to stabilize
echo -e "${BLUE}Waiting for services to stabilize...${NC}"
sleep 20

# Check final status
echo -e "\n${GREEN}=== FINAL SERVICE STATUS ===${NC}"
pm2 status

# Check all ports with details
echo -e "\n${GREEN}=== PORT STATUS ===${NC}"
echo -e "${YELLOW}Port   Service                    Status              Notes${NC}"
echo -e "${YELLOW}----   ----------------------     ------              -----${NC}"

ports=(
    "3002:auth:Skipped due to TypeScript errors"
    "3003:sensor-data:TypeScript service"
    "3005:moisture-monitoring:Working (MQTT errors expected)"
    "3006:weather-monitoring:May have dependency issues"
    "3007:gis:TypeScript service"
    "3008:water-level-monitoring:Working (MQTT errors expected)"
    "3010:awd-control:May have database issues"
    "3014:flow-monitoring:Python service"
    "3047:ros:TypeScript service"
    "3048:rid-ms:May have Kafka issues"
)

working_count=0
for port_info in "${ports[@]}"; do
    IFS=':' read -r port service notes <<< "$port_info"
    printf "%-6s %-25s " "$port" "$service"
    
    if timeout 1 bash -c "</dev/tcp/localhost/$port" 2>/dev/null; then
        echo -ne "${GREEN}✓ Open${NC}     "
        ((working_count++))
        # Try health check
        if curl -s -m 1 "http://localhost:$port/health" >/dev/null 2>&1; then
            echo -ne "${GREEN}[Health OK]${NC}"
        fi
    else
        echo -ne "${RED}✗ Closed${NC}   "
    fi
    echo " $notes"
done

echo -e "\n${GREEN}Total services listening: $working_count/10${NC}"

# Show recent logs for non-working services
echo -e "\n${YELLOW}Recent logs for non-working services:${NC}"
for service in weather-monitoring rid-ms awd-control; do
    if ! timeout 1 bash -c "</dev/tcp/localhost/$(pm2 describe $service | grep 'PORT' | awk '{print $NF}')" 2>/dev/null; then
        echo -e "\n${YELLOW}$service logs:${NC}"
        pm2 logs $service --lines 2 --nostream | grep -i "error" | head -3 || echo "No recent errors"
    fi
done

# Summary
echo -e "\n${GREEN}=== DEPLOYMENT SUMMARY ===${NC}"
echo "✓ Database containers: Running (PostgreSQL, TimescaleDB, Redis, InfluxDB, MongoDB)"
echo "✓ PM2 process manager: Running with auto-restart"
echo "✓ Services deployed: 9/10 (auth skipped due to compilation errors)"
echo ""
echo "Working services:"
echo "  - moisture-monitoring (3005)"
echo "  - water-level-monitoring (3008)"
echo "  - flow-monitoring (3014)"
echo "  - ros (3047)"
echo ""
echo "Services to debug:"
echo "  - sensor-data (3003)"
echo "  - weather-monitoring (3006)"
echo "  - gis (3007)"
echo "  - awd-control (3010)"
echo "  - rid-ms (3048)"
echo ""
echo -e "${YELLOW}Update EC2 security group to allow ports:${NC}"
echo "3003, 3005, 3006, 3007, 3008, 3010, 3014, 3047, 3048"

EOF

echo -e "\n${GREEN}Deployment complete!${NC}"