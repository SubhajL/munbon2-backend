#!/bin/bash

# Complete deployment script for ALL microservices
# Usage: ./deploy-all-services-ec2.sh

set -e

# Configuration
EC2_IP="43.209.22.250"
SSH_KEY="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"
EC2_USER="ubuntu"
REMOTE_DIR="/home/ubuntu/munbon2-backend"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# All microservices
SERVICES=(
    "sensor-data:3001"
    "auth:3002"
    "moisture-monitoring:3003"
    "weather-monitoring:3004"
    "water-level-monitoring:3005"
    "gis:3006"
    "ros:3012"
    "rid-ms:3011"
    "awd-control:3013"
    "flow-monitoring:3014"
)

echo -e "${BLUE}Deploying ALL microservices to EC2 at $EC2_IP...${NC}"

# Create deployment script
cat > deploy-all.sh << 'EOF'
#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

# Start all database containers
echo -e "${BLUE}Starting all database services...${NC}"
docker-compose up -d postgres timescaledb redis influxdb mongodb

# Wait for databases
echo -e "${BLUE}Waiting for databases to be ready...${NC}"
sleep 20

# Create PM2 ecosystem file for all services
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
        PORT: 3001,
        TIMESCALEDB_HOST: 'localhost',
        TIMESCALEDB_PORT: 5433,
        REDIS_HOST: 'localhost'
      }
    },
    {
      name: 'auth',
      cwd: './services/auth',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: 3002,
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: 5434
      }
    },
    {
      name: 'moisture-monitoring',
      cwd: './services/moisture-monitoring',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: 3003,
        TIMESCALEDB_HOST: 'localhost',
        INFLUXDB_HOST: 'localhost'
      }
    },
    {
      name: 'weather-monitoring',
      cwd: './services/weather-monitoring',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: 3004,
        TIMESCALEDB_HOST: 'localhost'
      }
    },
    {
      name: 'water-level-monitoring',
      cwd: './services/water-level-monitoring',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: 3005,
        TIMESCALEDB_HOST: 'localhost'
      }
    },
    {
      name: 'gis',
      cwd: './services/gis',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: 3006,
        POSTGRES_HOST: 'localhost',
        POSTGRES_PORT: 5434
      }
    },
    {
      name: 'ros',
      cwd: './services/ros',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: 3012,
        POSTGRES_HOST: 'localhost'
      }
    },
    {
      name: 'rid-ms',
      cwd: './services/rid-ms',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: 3011,
        POSTGRES_HOST: 'localhost'
      }
    },
    {
      name: 'awd-control',
      cwd: './services/awd-control',
      script: 'npm',
      args: 'run dev',
      env: {
        NODE_ENV: 'production',
        PORT: 3013,
        TIMESCALEDB_HOST: 'localhost',
        REDIS_HOST: 'localhost'
      }
    },
    {
      name: 'flow-monitoring',
      cwd: './services/flow-monitoring',
      script: 'python',
      args: 'src/main.py',
      interpreter: 'python3',
      env: {
        NODE_ENV: 'production',
        PORT: 3014,
        INFLUXDB_HOST: 'localhost'
      }
    }
  ]
}
EOFPM2

# Install dependencies for all Node.js services
NODE_SERVICES=("sensor-data" "auth" "moisture-monitoring" "weather-monitoring" "water-level-monitoring" "gis" "ros" "rid-ms" "awd-control")

for service in "${NODE_SERVICES[@]}"; do
    if [ -d "services/$service" ]; then
        echo -e "${BLUE}Installing dependencies for $service...${NC}"
        cd "services/$service"
        npm install
        cd ../..
    fi
done

# Setup Python service (flow-monitoring)
if [ -d "services/flow-monitoring" ]; then
    echo -e "${BLUE}Setting up flow-monitoring Python service...${NC}"
    cd "services/flow-monitoring"
    python3 -m venv venv || true
    source venv/bin/activate
    pip install -r requirements.txt || true
    cd ../..
fi

# Copy environment files
echo -e "${BLUE}Setting up environment files...${NC}"
for service in "${NODE_SERVICES[@]}"; do
    if [ -f "services/$service/.env.example" ] && [ ! -f "services/$service/.env" ]; then
        cp "services/$service/.env.example" "services/$service/.env"
        echo "Created .env for $service"
    fi
done

# Start all services with PM2
echo -e "${BLUE}Starting all services with PM2...${NC}"
pm2 delete all || true
pm2 start ecosystem.config.js
pm2 save

echo -e "${GREEN}All services deployed successfully!${NC}"
echo -e "${BLUE}Service Status:${NC}"
pm2 status

echo -e "\n${YELLOW}Database containers:${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo -e "\n${GREEN}Available endpoints:${NC}"
echo "- Sensor Data API: http://$(hostname -I | awk '{print $1}'):3001"
echo "- Auth Service: http://$(hostname -I | awk '{print $1}'):3002"
echo "- Moisture Monitoring: http://$(hostname -I | awk '{print $1}'):3003"
echo "- Weather Monitoring: http://$(hostname -I | awk '{print $1}'):3004"
echo "- Water Level Monitoring: http://$(hostname -I | awk '{print $1}'):3005"
echo "- GIS Service: http://$(hostname -I | awk '{print $1}'):3006"
echo "- RID-MS Service: http://$(hostname -I | awk '{print $1}'):3011"
echo "- ROS Service: http://$(hostname -I | awk '{print $1}'):3012"
echo "- AWD Control: http://$(hostname -I | awk '{print $1}'):3013"
echo "- Flow Monitoring: http://$(hostname -I | awk '{print $1}'):3014"
EOF

# Copy deployment script to EC2
echo -e "${BLUE}Copying deployment script to EC2...${NC}"
scp -o StrictHostKeyChecking=no -i "$SSH_KEY" deploy-all.sh "$EC2_USER@$EC2_IP:~/"

# Execute deployment
echo -e "${BLUE}Executing deployment of all services...${NC}"
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" 'bash ~/deploy-all.sh'

# Cleanup
rm deploy-all.sh

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}All Microservices Deployed!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\n${BLUE}Services running:${NC}"
for service_info in "${SERVICES[@]}"; do
    IFS=':' read -r service port <<< "$service_info"
    echo "- $service: http://$EC2_IP:$port"
done

echo -e "\n${BLUE}Databases:${NC}"
echo "- PostgreSQL (PostGIS): Port 5434"
echo "- TimescaleDB: Port 5433"
echo "- Redis: Port 6379"
echo "- InfluxDB: Port 8086"
echo "- MongoDB: Port 27017"

echo -e "\n${YELLOW}To check status:${NC}"
echo "ssh -i $SSH_KEY $EC2_USER@$EC2_IP 'pm2 status'"
echo -e "\n${YELLOW}To view logs:${NC}"
echo "ssh -i $SSH_KEY $EC2_USER@$EC2_IP 'pm2 logs'"
echo -e "\n${YELLOW}To check Docker containers:${NC}"
echo "ssh -i $SSH_KEY $EC2_USER@$EC2_IP 'docker ps'"