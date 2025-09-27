#!/bin/bash

# Deploy unified sensor endpoints to EC2
# Handles moisture, water level, and AOS weather data on same server

echo "🚀 Deploying Unified Sensor Endpoints to EC2"
echo "==========================================="

# Load environment variables
source load-ec2-config.sh

# Configuration
EC2_HOST=${EC2_HOST:-43.208.201.191}
EC2_USER="ubuntu"
KEY_PATH="~/dev/th-lab01.pem"
REMOTE_APP_DIR="/home/ubuntu/sensor-data-unified"
SERVICE_NAME="unified-sensor"

echo "📍 Target: $EC2_USER@$EC2_HOST"
echo ""

# Step 1: Create AOS table if needed
echo "📊 Creating AOS weather table..."
scp -i $KEY_PATH services/sensor-data/sql/create-aos-table.sql $EC2_USER@$EC2_HOST:/tmp/
ssh -i $KEY_PATH $EC2_USER@$EC2_HOST << 'EOF'
  docker exec postgres_timescale_postgis psql -U postgres -d sensor_data -f /tmp/create-aos-table.sql
  echo "✅ AOS weather table created/verified"
EOF

# Step 2: Stop existing service
echo ""
echo "🛑 Stopping existing moisture service..."
ssh -i $KEY_PATH $EC2_USER@$EC2_HOST << EOF
  pm2 stop moisture-http 2>/dev/null || true
  pm2 delete moisture-http 2>/dev/null || true
EOF

# Step 3: Create remote directory
echo ""
echo "📁 Creating remote directory..."
ssh -i $KEY_PATH $EC2_USER@$EC2_HOST "mkdir -p $REMOTE_APP_DIR"

# Step 4: Copy unified server file
echo ""
echo "📤 Copying unified server..."
scp -i $KEY_PATH services/sensor-data/src/unified-sensor-server.js $EC2_USER@$EC2_HOST:$REMOTE_APP_DIR/

# Step 5: Create package.json
echo ""
echo "📦 Creating package.json..."
cat > /tmp/package.json << 'PACKAGE'
{
  "name": "unified-sensor-endpoints",
  "version": "2.0.0",
  "description": "Unified HTTP endpoints for moisture, water level, and AOS data",
  "main": "unified-sensor-server.js",
  "scripts": {
    "start": "node unified-sensor-server.js"
  },
  "dependencies": {
    "express": "^4.18.2",
    "pg": "^8.11.3",
    "pino": "^8.16.1",
    "pino-pretty": "^10.2.3",
    "dotenv": "^16.3.1"
  }
}
PACKAGE
scp -i $KEY_PATH /tmp/package.json $EC2_USER@$EC2_HOST:$REMOTE_APP_DIR/

# Step 6: Install dependencies and start service
echo ""
echo "📥 Installing dependencies and starting service..."
ssh -i $KEY_PATH $EC2_USER@$EC2_HOST << EOF
  cd $REMOTE_APP_DIR
  npm install
  
  # Create .env file
  cat > .env << 'ENVFILE'
DB_HOST=localhost
DB_PORT=5432
DB_NAME=sensor_data
DB_USER=postgres
DB_PASSWORD=__ROTATED_DB_PASSWORD__
HTTP_PORT=8080
ENVFILE

  # Start with PM2
  pm2 start unified-sensor-server.js --name "$SERVICE_NAME" --env production
  pm2 save
  
  echo "✅ Unified sensor service started"
EOF

# Step 7: Test endpoints
echo ""
echo "🧪 Testing endpoints..."
sleep 3

# Test health
echo "Testing health endpoint..."
curl -s http://$EC2_HOST:8080/health | jq .

# Test root
echo ""
echo "Testing root endpoint..."
curl -s http://$EC2_HOST:8080/ | jq .

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📡 Available endpoints with recommended tokens:"
echo ""
echo "  Moisture endpoints:"
echo "  - Field sensors: http://$EC2_HOST:8080/api/sensor-data/moisture/munbon-moisture-field"
echo "  - Gate sensors: http://$EC2_HOST:8080/api/sensor-data/moisture/munbon-moisture-gate"
echo ""
echo "  Water Level endpoints:"
echo "  - Gate levels: http://$EC2_HOST:8080/api/sensor-data/water-level/munbon-level-gate"
echo "  - Canal levels: http://$EC2_HOST:8080/api/sensor-data/water-level/munbon-level-canal"
echo ""
echo "  AOS Weather endpoints:"
echo "  - Field stations: http://$EC2_HOST:8080/api/sensor-data/aos/munbon-aos-field"
echo "  - Gate stations: http://$EC2_HOST:8080/api/sensor-data/aos/munbon-aos-gate"
echo ""
echo "  Monitoring endpoints:"
echo "  - Statistics: http://$EC2_HOST:8080/api/stats"
echo "  - Health: http://$EC2_HOST:8080/health"
echo ""
echo "📊 View logs: ssh -i $KEY_PATH $EC2_USER@$EC2_HOST 'pm2 logs $SERVICE_NAME'"
echo "📊 View status: ssh -i $KEY_PATH $EC2_USER@$EC2_HOST 'pm2 status'"