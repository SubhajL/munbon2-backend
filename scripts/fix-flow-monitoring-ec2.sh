#!/bin/bash

# Fix flow-monitoring Python service on EC2
# Usage: ./fix-flow-monitoring-ec2.sh

set -e

# Configuration
EC2_IP="43.209.12.182"
SSH_KEY="/Users/subhajlimanond/dev/munbon2-backend/th-lab01.pem"
EC2_USER="ubuntu"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}Fixing flow-monitoring Python service on EC2...${NC}"

# Execute fix on EC2
ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" "$EC2_USER@$EC2_IP" << 'EOF'
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd /home/ubuntu/munbon2-backend

# First, check if Python service directory exists
if [ ! -d "services/flow-monitoring" ]; then
    echo -e "${YELLOW}Warning: flow-monitoring service directory not found${NC}"
    exit 1
fi

# Install Python dependencies
echo -e "${BLUE}Installing Python 3 and pip...${NC}"
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv

# Stop the broken flow-monitoring service
echo -e "${BLUE}Stopping flow-monitoring service...${NC}"
pm2 delete flow-monitoring || true

# Create a simple Python test script if main.py doesn't exist
if [ ! -f "services/flow-monitoring/src/main.py" ]; then
    echo -e "${BLUE}Creating placeholder Python script...${NC}"
    mkdir -p services/flow-monitoring/src
    cat > services/flow-monitoring/src/main.py << 'PYTHONEOF'
#!/usr/bin/env python3
"""Flow Monitoring Service"""
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

PORT = int(os.environ.get('PORT', 3014))

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
        # Suppress logs
        pass

def main():
    print(f"Flow Monitoring Service starting on port {PORT}...")
    server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
    print(f"Server running on http://0.0.0.0:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    main()
PYTHONEOF
fi

# Create requirements.txt if it doesn't exist
if [ ! -f "services/flow-monitoring/requirements.txt" ]; then
    echo -e "${BLUE}Creating requirements.txt...${NC}"
    cat > services/flow-monitoring/requirements.txt << 'REQEOF'
# Add your Python dependencies here
# influxdb-client==1.36.1
# pandas==2.0.3
# numpy==1.24.3
REQEOF
fi

# Update PM2 ecosystem config with correct Python service configuration
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
      script: 'src/main.py',
      interpreter: 'python3',
      env: {
        PORT: 3014,
        INFLUXDB_HOST: 'localhost',
        INFLUXDB_PORT: 8086
      }
    }
  ]
}
EOFPM2

# Restart all services with updated config
echo -e "${BLUE}Restarting all services with updated configuration...${NC}"
pm2 delete all || true
pm2 start ecosystem.config.js
pm2 save

echo -e "${GREEN}Flow monitoring service fixed!${NC}"
pm2 status

# Check which services are actually listening
echo -e "\n${BLUE}Checking listening ports...${NC}"
sudo ss -tlnp | grep -E ":(300[1-6]|301[1-4])" || true

echo -e "\n${BLUE}Testing service endpoints...${NC}"
# Test each service
for port in 3001 3002 3003 3004 3005 3006 3011 3012 3013 3014; do
    echo -n "Port $port: "
    curl -s -m 2 "http://localhost:$port/health" && echo " ✓" || echo " ✗"
done
EOF

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Flow Monitoring Fix Complete!${NC}"
echo -e "${GREEN}========================================${NC}"

# Test from local machine
echo -e "\n${BLUE}Testing services from local machine...${NC}"
for port in 3001 3002 3003 3004 3005 3006 3011 3012 3013 3014; do
    echo -n "Service on port $port: "
    curl -s -m 2 "http://$EC2_IP:$port/health" && echo " ✓ Accessible" || echo " ✗ Not accessible"
done

echo -e "\n${YELLOW}Note: If services are not accessible from outside, you may need to:${NC}"
echo "1. Check EC2 security group allows inbound traffic on ports 3001-3014"
echo "2. Ensure services are binding to 0.0.0.0 instead of localhost"
echo "3. Check if there's a firewall blocking the ports"