#!/bin/bash

# Install missing dependencies for all services
# Usage: ./install-missing-dependencies-ec2.sh

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

echo -e "${BLUE}Installing missing dependencies on EC2...${NC}"

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
echo -e "${BLUE}Stopping all services...${NC}"
pm2 stop all

# Install missing dependencies for each service
echo -e "${BLUE}Installing missing npm dependencies...${NC}"

# Weather monitoring needs express-validator
echo -e "${YELLOW}Installing express-validator for weather-monitoring...${NC}"
cd services/weather-monitoring
npm install express-validator --save
cd ../..

# Moisture and water-level monitoring need socket.io redis adapter
echo -e "${YELLOW}Installing @socket.io/redis-adapter for monitoring services...${NC}"
cd services/moisture-monitoring
npm install @socket.io/redis-adapter socket.io --save
cd ../..

cd services/water-level-monitoring
npm install @socket.io/redis-adapter socket.io --save
cd ../..

# GIS service might need multer
echo -e "${YELLOW}Installing multer for GIS service...${NC}"
cd services/gis
npm install multer @types/multer --save
cd ../..

# Auth service needs type definitions
echo -e "${YELLOW}Installing type definitions for auth service...${NC}"
cd services/auth
npm install @types/node @types/express @types/passport --save-dev
cd ../..

# Fix Python dependencies for flow-monitoring
echo -e "${YELLOW}Installing Python dependencies for flow-monitoring...${NC}"
cd services/flow-monitoring
source venv/bin/activate
pip install prometheus_client aiofiles httpx
# Update the simple HTTP server to not use missing modules
cat > src/main.py << 'PYTHONEOF'
#!/usr/bin/env python3
"""Flow Monitoring Service - Simple HTTP Server"""
import os
import time
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

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
        elif self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            metrics = f"# HELP flow_monitoring_up Flow monitoring service status\n"
            metrics += f"# TYPE flow_monitoring_up gauge\n"
            metrics += f"flow_monitoring_up 1\n"
            self.wfile.write(metrics.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")

def main():
    print(f"Flow Monitoring Service starting on {HOST}:{PORT}...")
    server = HTTPServer((HOST, PORT), HealthHandler)
    print(f"Server running on http://{HOST}:{PORT}")
    print(f"Health check: http://{HOST}:{PORT}/health")
    print(f"Metrics: http://{HOST}:{PORT}/metrics")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()

if __name__ == "__main__":
    main()
PYTHONEOF
cd ../..

# Fix sensor-data database connection
echo -e "${YELLOW}Fixing sensor-data database credentials...${NC}"
if [ -f "services/sensor-data/.env" ]; then
    # Add database URL
    echo "DATABASE_URL=postgresql://postgres:postgres123@localhost:5433/sensor_data" >> services/sensor-data/.env
fi

# Create databases if they don't exist
echo -e "${BLUE}Creating databases...${NC}"
docker exec -it munbon-postgres psql -U postgres -c "CREATE DATABASE auth_db;" 2>/dev/null || true
docker exec -it munbon-postgres psql -U postgres -c "CREATE DATABASE gis_db;" 2>/dev/null || true
docker exec -it munbon-postgres psql -U postgres -c "CREATE DATABASE rid_db;" 2>/dev/null || true
docker exec -it munbon-postgres psql -U postgres -c "CREATE DATABASE weather_db;" 2>/dev/null || true
docker exec -it munbon-timescaledb psql -U postgres -c "CREATE DATABASE sensor_data;" 2>/dev/null || true

# Install PostGIS extension in gis_db
echo -e "${BLUE}Installing PostGIS extension...${NC}"
docker exec -it munbon-postgres psql -U postgres -d gis_db -c "CREATE EXTENSION IF NOT EXISTS postgis;" 2>/dev/null || true

# Restart all services
echo -e "${BLUE}Starting all services...${NC}"
pm2 start all

# Wait for services to start
sleep 10

# Check status
echo -e "\n${GREEN}Service status after dependency installation:${NC}"
pm2 status

# Test endpoints
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
    else
        echo -e "${RED}✗ Not responding${NC}"
        # Show last error
        pm2 logs "$service_name" --lines 1 --nostream 2>/dev/null | grep -i error | tail -1 | sed 's/^/  /'
    fi
done

# Check listening ports
echo -e "\n${BLUE}Services listening on ports:${NC}"
sudo ss -tlnp | grep -E ":(300[1-6]|301[1-4])" | awk '{print $4 " - " $6}'
EOF

echo -e "\n${GREEN}Dependency installation complete!${NC}"