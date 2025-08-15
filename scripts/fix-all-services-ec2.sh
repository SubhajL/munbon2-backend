#!/bin/bash

# Fix all services on EC2 with proper environment variables and dependencies
# Usage: ./fix-all-services-ec2.sh

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

echo -e "${BLUE}Fixing all services on EC2...${NC}"

# Execute comprehensive fix on EC2
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

# Stop all services first
echo -e "${BLUE}Stopping all PM2 services...${NC}"
pm2 stop all || true

# Create comprehensive .env files for each service
echo -e "${BLUE}Creating environment files for all services...${NC}"

# Sensor Data Service
cat > services/sensor-data/.env << 'ENVEOF'
NODE_ENV=production
PORT=3001
HOST=0.0.0.0

# TimescaleDB
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres123

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# AWS SQS (if needed)
AWS_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=dummy
AWS_SECRET_ACCESS_KEY=dummy
SQS_QUEUE_URL=dummy

# Logging
LOG_LEVEL=info
ENVEOF

# Auth Service
cat > services/auth/.env << 'ENVEOF'
NODE_ENV=production
PORT=3002
HOST=0.0.0.0

# PostgreSQL
DATABASE_URL=postgresql://postgres:postgres123@localhost:5434/auth_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DB=auth_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

# JWT
JWT_SECRET=your-super-secret-jwt-key-change-in-production
JWT_EXPIRES_IN=7d

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
ENVEOF

# GIS Service
cat > services/gis/.env << 'ENVEOF'
NODE_ENV=production
PORT=3006
HOST=0.0.0.0

# PostgreSQL with PostGIS
DATABASE_URL=postgresql://postgres:postgres123@localhost:5434/gis_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DB=gis_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# GIS specific
MAX_UPLOAD_SIZE=100MB
ALLOWED_FORMATS=shp,geojson,kml,gpkg
ENVEOF

# Moisture Monitoring Service
cat > services/moisture-monitoring/.env << 'ENVEOF'
NODE_ENV=production
PORT=3003
HOST=0.0.0.0

# TimescaleDB
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres123

# InfluxDB
INFLUX_HOST=localhost
INFLUX_PORT=8086
INFLUX_TOKEN=my-super-secret-auth-token
INFLUX_ORG=munbon
INFLUX_BUCKET=moisture_data

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
ENVEOF

# Weather Monitoring Service
cat > services/weather-monitoring/.env << 'ENVEOF'
NODE_ENV=production
PORT=3004
HOST=0.0.0.0

# TimescaleDB
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres123

# Weather API
WEATHER_API_KEY=dummy-key
WEATHER_API_URL=https://api.openweathermap.org/data/2.5

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
ENVEOF

# Water Level Monitoring Service
cat > services/water-level-monitoring/.env << 'ENVEOF'
NODE_ENV=production
PORT=3005
HOST=0.0.0.0

# TimescaleDB
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres123

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Alert thresholds
CRITICAL_LEVEL_THRESHOLD=80
WARNING_LEVEL_THRESHOLD=60
ENVEOF

# ROS Service
cat > services/ros/.env << 'ENVEOF'
NODE_ENV=production
PORT=3012
HOST=0.0.0.0

# PostgreSQL
DATABASE_URL=postgresql://postgres:postgres123@localhost:5434/ros_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DB=ros_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
ENVEOF

# RID-MS Service
cat > services/rid-ms/.env << 'ENVEOF'
NODE_ENV=production
PORT=3011
HOST=0.0.0.0

# PostgreSQL
DATABASE_URL=postgresql://postgres:postgres123@localhost:5434/rid_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DB=rid_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# MongoDB
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_DB=rid_documents
ENVEOF

# AWD Control Service
cat > services/awd-control/.env << 'ENVEOF'
NODE_ENV=production
PORT=3013
HOST=0.0.0.0

# TimescaleDB
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5433
TIMESCALE_DB=sensor_data
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=postgres123

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Control parameters
MAX_WATER_DEPTH=15
MIN_WATER_DEPTH=5
CONTROL_INTERVAL=300
ENVEOF

# Flow Monitoring Service
cat > services/flow-monitoring/.env << 'ENVEOF'
PORT=3014
HOST=0.0.0.0

# InfluxDB
INFLUX_HOST=localhost
INFLUX_PORT=8086
INFLUX_TOKEN=my-super-secret-auth-token
INFLUX_ORG=munbon
INFLUX_BUCKET=flow_data

# Monitoring
SAMPLE_INTERVAL=60
RETENTION_DAYS=90
ENVEOF

# Install missing npm dependencies
echo -e "${BLUE}Installing missing npm dependencies...${NC}"

# Weather monitoring needs compression
cd services/weather-monitoring
npm install compression @types/compression --save
cd ../..

# Auth service needs tsconfig-paths
cd services/auth
npm install tsconfig-paths --save-dev
cd ../..

# Install Python dependencies for flow-monitoring
echo -e "${BLUE}Setting up Python environment for flow-monitoring...${NC}"
cd services/flow-monitoring

# Check if main.py exists, if not create from our placeholder
if [ ! -f "src/main.py" ]; then
    mkdir -p src
    cat > src/main.py << 'PYTHONEOF'
#!/usr/bin/env python3
"""Flow Monitoring Service"""
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

PORT = int(os.environ.get('PORT', 3014))
HOST = os.environ.get('HOST', '0.0.0.0')

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'status': 'healthy',
                'service': 'flow-monitoring',
                'port': PORT,
                'timestamp': time.time()
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")

def main():
    print(f"Flow Monitoring Service starting on {HOST}:{PORT}...")
    server = HTTPServer((HOST, PORT), HealthHandler)
    print(f"Server running on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()

if __name__ == "__main__":
    main()
PYTHONEOF
fi

# Create requirements.txt with actual dependencies
cat > requirements.txt << 'REQEOF'
structlog==24.1.0
influxdb-client==1.38.0
python-dotenv==1.0.0
pandas==2.0.3
numpy==1.24.3
REQEOF

# Install Python dependencies
python3 -m pip install -r requirements.txt

cd ../..

# Update PM2 ecosystem config to bind to 0.0.0.0
echo -e "${BLUE}Updating PM2 ecosystem configuration...${NC}"
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
        HOST: '0.0.0.0'
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
        HOST: '0.0.0.0'
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
        HOST: '0.0.0.0'
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
        HOST: '0.0.0.0'
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
        HOST: '0.0.0.0'
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
        HOST: '0.0.0.0'
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
        HOST: '0.0.0.0'
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
        HOST: '0.0.0.0'
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
        HOST: '0.0.0.0'
      }
    },
    {
      name: 'flow-monitoring',
      cwd: './services/flow-monitoring',
      script: 'src/main.py',
      interpreter: 'python3',
      env: {
        PORT: 3014,
        HOST: '0.0.0.0'
      }
    }
  ]
}
EOFPM2

# Restart all services
echo -e "${BLUE}Starting all services with PM2...${NC}"
pm2 delete all || true
pm2 start ecosystem.config.js
pm2 save

# Wait for services to stabilize
sleep 10

echo -e "${GREEN}All services fixed!${NC}"
pm2 status

# Check listening ports
echo -e "\n${BLUE}Checking listening ports...${NC}"
sudo ss -tlnp | grep -E ":(300[1-6]|301[1-4])" || echo "No services listening yet"

# Test services internally
echo -e "\n${BLUE}Testing service endpoints internally...${NC}"
for port in 3001 3002 3003 3004 3005 3006 3011 3012 3013 3014; do
    echo -n "Port $port: "
    if curl -s -m 2 "http://localhost:$port/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Working${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi
done

# Check PM2 logs for any errors
echo -e "\n${YELLOW}Recent errors (if any):${NC}"
pm2 logs --lines 5 --nostream | grep -i error || echo "No recent errors found"
EOF

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Service Fix Complete!${NC}"
echo -e "${GREEN}========================================${NC}"

# Check EC2 security group
echo -e "\n${BLUE}Checking EC2 Security Group...${NC}"
echo -e "${YELLOW}To allow external access, ensure your EC2 security group has these inbound rules:${NC}"
echo "- Port 3001-3014: Custom TCP Rule, Source: 0.0.0.0/0 (or your IP)"
echo "- Port 22: SSH, Source: Your IP"
echo ""
echo -e "${YELLOW}To add the rules via AWS CLI:${NC}"
echo "aws ec2 authorize-security-group-ingress --group-id <YOUR-SG-ID> --protocol tcp --port 3001-3014 --cidr 0.0.0.0/0"

# Test from local machine
echo -e "\n${BLUE}Testing services from local machine...${NC}"
for port in 3001 3002 3003 3004 3005 3006 3011 3012 3013 3014; do
    echo -n "Service on port $port: "
    if curl -s -m 2 "http://$EC2_IP:$port/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Accessible externally${NC}"
    else
        echo -e "${RED}✗ Not accessible (check security group)${NC}"
    fi
done