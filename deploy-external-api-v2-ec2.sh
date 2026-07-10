#!/bin/bash

# Wave 1.11 guard: the old leaked credential was rotated; a real one MUST come
# from the environment, and the redaction sentinel must never reach a live system.
: "${DB_PASSWORD:?set DB_PASSWORD in the environment (the old leaked value was rotated)}"
case "$DB_PASSWORD" in *ROTATED_DB_PASSWORD*) echo "refusing to deploy the redaction sentinel as a credential" >&2; exit 1;; esac


# Deploy External API V2.0 to EC2
# Implements the exact same API as the AWS Lambda version but on EC2

echo "🚀 Deploying External API V2.0 to EC2"
echo "====================================="

# Load environment variables
source load-ec2-config.sh

# Configuration
EC2_HOST=${EC2_HOST:-43.208.201.191}
EC2_USER="ubuntu"
KEY_PATH="~/dev/th-lab01.pem"
REMOTE_APP_DIR="/home/ubuntu/external-api-v2"
SERVICE_NAME="external-api-v2"

echo "📍 Target: $EC2_USER@$EC2_HOST"
echo ""

# Step 1: Stop existing services that might conflict
echo "🛑 Stopping any existing services..."
ssh -i $KEY_PATH $EC2_USER@$EC2_HOST << EOF
  # Stop the unified sensor service if running
  pm2 stop unified-sensor 2>/dev/null || true
  pm2 delete unified-sensor 2>/dev/null || true
  
  # Stop any existing external API service
  pm2 stop external-api-v2 2>/dev/null || true
  pm2 delete external-api-v2 2>/dev/null || true
EOF

# Step 2: Create remote directory
echo ""
echo "📁 Creating remote directory..."
ssh -i $KEY_PATH $EC2_USER@$EC2_HOST "mkdir -p $REMOTE_APP_DIR/src"

# Step 3: Copy files
echo ""
echo "📤 Copying files..."
scp -i $KEY_PATH services/external-api/package.json $EC2_USER@$EC2_HOST:$REMOTE_APP_DIR/
scp -i $KEY_PATH services/external-api/src/external-api-v2-ec2-multi-db.js $EC2_USER@$EC2_HOST:$REMOTE_APP_DIR/src/

# Step 4: Install dependencies and start service
echo ""
echo "📥 Installing dependencies and starting service..."
ssh -i $KEY_PATH $EC2_USER@$EC2_HOST << EOF
  cd $REMOTE_APP_DIR
  npm install
  
  # Create .env file
  cat > .env << 'ENVFILE'
# PostgreSQL for Water Level & Moisture
DB_HOST=localhost
DB_PORT=5432
DB_NAME=sensor_data
DB_USER=postgres
DB_PASSWORD=__DB_PASSWORD_FROM_DEPLOY_ENV__

# MSSQL for AOS Weather Data
MSSQL_SERVER=moonup.hopto.org
MSSQL_PORT=1433
MSSQL_DATABASE=db_scada
MSSQL_USER=sa
MSSQL_PASSWORD=bangkok1234

# Server Port
PORT=8081
ENVFILE
  sed -i "s/__DB_PASSWORD_FROM_DEPLOY_ENV__/${DB_PASSWORD}/" .env

  # Start with PM2
  pm2 start src/external-api-v2-ec2-multi-db.js --name "$SERVICE_NAME" --env production
  pm2 save
  
  echo "✅ External API V2 service started"
EOF

# Step 5: Test endpoints
echo ""
echo "🧪 Testing endpoints..."
sleep 3

# Test health
echo "Testing health endpoint..."
curl -s http://$EC2_HOST:8081/health | jq .

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📡 External API V2.0 Endpoints (Multi-Database Implementation):"
echo ""
echo "Base URL: http://$EC2_HOST:8081/api/v1"
echo ""
echo "Required Header: X-API-Key"
echo "Valid API Keys:"
echo "  - rid-ms-prod-key1 (RID Main System)"
echo "  - tmd-weather-key2 (Thai Meteorological Department)"
echo "  - university-key3 (University Research)"
echo ""
echo "💾 Database Sources:"
echo "  - Water Level & Moisture: TimescaleDB (PostgreSQL)"
echo "  - AOS Weather: SCADA Database (MSSQL at moonup.hopto.org)"
echo ""
echo "Water Level Endpoints (TimescaleDB):"
echo "  GET http://$EC2_HOST:8081/api/v1/public/water-levels/latest"
echo "  GET http://$EC2_HOST:8081/api/v1/public/water-levels/timeseries?date=DD/MM/YYYY"
echo "  GET http://$EC2_HOST:8081/api/v1/public/water-levels/statistics?date=DD/MM/YYYY"
echo ""
echo "Moisture Endpoints (TimescaleDB):"
echo "  GET http://$EC2_HOST:8081/api/v1/public/moisture/latest"
echo "  GET http://$EC2_HOST:8081/api/v1/public/moisture/timeseries?date=DD/MM/YYYY"
echo "  GET http://$EC2_HOST:8081/api/v1/public/moisture/statistics?date=DD/MM/YYYY"
echo ""
echo "AOS Weather Endpoints (MSSQL SCADA):"
echo "  GET http://$EC2_HOST:8081/api/v1/public/aos/latest"
echo "  GET http://$EC2_HOST:8081/api/v1/public/aos/timeseries?date=DD/MM/YYYY"
echo "  GET http://$EC2_HOST:8081/api/v1/public/aos/statistics?date=DD/MM/YYYY"
echo ""
echo "📊 View logs: ssh -i $KEY_PATH $EC2_USER@$EC2_HOST 'pm2 logs $SERVICE_NAME'"
echo "📊 View status: ssh -i $KEY_PATH $EC2_USER@$EC2_HOST 'pm2 status'"