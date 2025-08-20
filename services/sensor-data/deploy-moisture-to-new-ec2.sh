#!/bin/bash

# Deployment script for moisture HTTP server on NEW EC2 instance
# This script deploys the moisture endpoint to the new EC2 IP: 43.208.201.191

set -e

EC2_HOST="43.208.201.191"
EC2_USER="ubuntu"
PEM_FILE="$HOME/dev/th-lab01.pem"

echo "🚀 Starting deployment of Moisture HTTP Server to NEW EC2: $EC2_HOST"

# 1. First check if EC2 is accessible
echo "🔍 Checking EC2 connectivity..."
if ! ssh -i "$PEM_FILE" -o ConnectTimeout=5 "$EC2_USER@$EC2_HOST" "echo 'Connected successfully'" 2>&1 | grep -q "Connected successfully"; then
    echo "❌ Cannot connect to EC2. Please check:"
    echo "   - PEM file exists at: $PEM_FILE"
    echo "   - EC2 instance is running"
    echo "   - Security group allows SSH from your IP"
    exit 1
fi

echo "✅ EC2 is accessible"

# 2. Copy the moisture HTTP server file to EC2
echo "📦 Preparing moisture HTTP server..."

# Create updated version with new EC2 IP
cat > /tmp/simple-http-server-new-ec2.ts << 'EOF'
import express from 'express';
import { SQSClient, SendMessageCommand } from '@aws-sdk/client-sqs';
import * as dotenv from 'dotenv';
import pino from 'pino';

dotenv.config();

const app = express();
app.use(express.json());
app.use(express.text());

const logger = pino({
  transport: {
    target: 'pino-pretty',
    options: { colorize: true }
  }
});

// SQS client
const sqsClient = new SQSClient({
  region: process.env.AWS_REGION || 'ap-southeast-1'
});

const SQS_QUEUE_URL = process.env.SQS_QUEUE_URL || 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';

// Middleware to log all incoming requests
app.use((req, res, next) => {
  logger.info({
    method: req.method,
    url: req.url,
    headers: req.headers,
    body: req.body
  }, 'Incoming request');
  next();
});

// Simple HTTP endpoint for moisture data
app.post('/api/sensor-data/moisture/:token', async (req, res) => {
  try {
    const { token } = req.params;
    const data = req.body;
    
    logger.info({ token, data }, 'Received moisture data via HTTP');
    
    // Prepare message for SQS
    const message = {
      timestamp: new Date().toISOString(),
      token: token,
      tokenGroup: 'moisture-munbon',
      sensorType: 'moisture',
      sensorId: data.gw_id || data.gateway_id || data.sensor_id,
      location: { 
        lat: parseFloat(data.latitude) || 0, 
        lng: parseFloat(data.longitude) || 0 
      },
      data: data,
      sourceIp: req.ip,
      metadata: {}
    };
    
    // Send to SQS
    const command = new SendMessageCommand({
      QueueUrl: SQS_QUEUE_URL,
      MessageBody: JSON.stringify(message)
    });
    
    await sqsClient.send(command);
    
    logger.info({ 
      token, 
      gateway_id: data.gw_id || data.gateway_id,
      sqsMessageId: message.timestamp 
    }, 'Sent to SQS successfully');
    
    res.status(200).json({ status: 'success', message: 'Data received' });
  } catch (error) {
    logger.error({ error }, 'Failed to process moisture data');
    res.status(500).json({ status: 'error', message: 'Internal server error' });
  }
});

// Health check
app.get('/health', (_req, res) => {
  res.status(200).json({ 
    status: 'healthy',
    service: 'moisture-http-endpoint',
    timestamp: new Date().toISOString(),
    ec2_ip: '43.208.201.191'
  });
});

// Root endpoint for testing
app.get('/', (_req, res) => {
  res.status(200).json({ 
    service: 'Munbon Moisture Data Ingestion',
    endpoints: {
      health: '/health',
      moisture: '/api/sensor-data/moisture/:token'
    },
    ec2_ip: '43.208.201.191'
  });
});

const PORT = parseInt(process.env.HTTP_PORT || '8080');

app.listen(PORT, '0.0.0.0', () => {
  logger.info(`🚀 Moisture HTTP server listening on port ${PORT}`);
  logger.info(`📡 Moisture endpoint: http://43.208.201.191:${PORT}/api/sensor-data/moisture/munbon-m2m-moisture`);
  logger.info(`🏥 Health check: http://43.208.201.191:${PORT}/health`);
});
EOF

# 3. Deploy to EC2
echo "🚀 Deploying to EC2..."

# Copy file to EC2
scp -i "$PEM_FILE" /tmp/simple-http-server-new-ec2.ts "$EC2_USER@$EC2_HOST:/tmp/"

# Execute deployment on EC2
ssh -i "$PEM_FILE" "$EC2_USER@$EC2_HOST" << 'REMOTE_SCRIPT'
set -e

echo "📂 Setting up project directory..."
mkdir -p ~/munbon2-backend/services/sensor-data/src
cd ~/munbon2-backend/services/sensor-data

# Copy the server file
cp /tmp/simple-http-server-new-ec2.ts src/simple-http-server.ts

# Check if package.json exists, if not create it
if [ ! -f package.json ]; then
    echo "📄 Creating package.json..."
    cat > package.json << 'PACKAGE_JSON'
{
  "name": "sensor-data-service",
  "version": "1.0.0",
  "description": "Moisture data ingestion service",
  "main": "src/simple-http-server.ts",
  "scripts": {
    "start": "ts-node src/simple-http-server.ts",
    "dev": "nodemon --exec ts-node src/simple-http-server.ts"
  },
  "dependencies": {
    "express": "^4.18.2",
    "@aws-sdk/client-sqs": "^3.400.0",
    "pino": "^8.15.0",
    "pino-pretty": "^10.2.0",
    "dotenv": "^16.3.1"
  },
  "devDependencies": {
    "@types/express": "^4.17.17",
    "typescript": "^5.2.2",
    "ts-node": "^10.9.1",
    "nodemon": "^3.0.1",
    "@types/node": "^20.5.0"
  }
}
PACKAGE_JSON
fi

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Create environment file
echo "⚙️ Creating environment configuration..."
cat > .env << 'ENV_FILE'
HTTP_PORT=8080
AWS_REGION=ap-southeast-1
SQS_QUEUE_URL=https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue
NODE_ENV=production
ENV_FILE

# Create PM2 ecosystem file
echo "⚙️ Creating PM2 configuration..."
cat > ecosystem.moisture.config.js << 'PM2_CONFIG'
module.exports = {
  apps: [{
    name: 'moisture-http',
    script: 'src/simple-http-server.ts',
    interpreter: 'npx',
    interpreter_args: 'ts-node',
    env: {
      HTTP_PORT: 8080,
      AWS_REGION: 'ap-southeast-1',
      SQS_QUEUE_URL: 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue',
      NODE_ENV: 'production'
    },
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '1G',
    log_date_format: 'YYYY-MM-DD HH:mm:ss',
    error_file: 'logs/moisture-http-error.log',
    out_file: 'logs/moisture-http-out.log',
    merge_logs: true
  }]
};
PM2_CONFIG

# Create logs directory
mkdir -p logs

# Install PM2 globally if not installed
if ! command -v pm2 &> /dev/null; then
    echo "📦 Installing PM2..."
    sudo npm install -g pm2
fi

# Stop any existing moisture-http process
echo "🛑 Stopping any existing moisture-http process..."
pm2 stop moisture-http 2>/dev/null || true
pm2 delete moisture-http 2>/dev/null || true

# Start with PM2
echo "🚀 Starting moisture HTTP server with PM2..."
pm2 start ecosystem.moisture.config.js

# Save PM2 configuration
pm2 save

# Setup PM2 to start on boot
pm2 startup systemd -u ubuntu --hp /home/ubuntu
sudo env PATH=$PATH:/usr/bin pm2 startup systemd -u ubuntu --hp /home/ubuntu

# Show status
pm2 status moisture-http

echo "✅ Deployment on EC2 complete!"
REMOTE_SCRIPT

# 4. Update security group
echo ""
echo "🔒 IMPORTANT: Ensure EC2 security group allows:"
echo "   - Port 8080 (HTTP) from 0.0.0.0/0 for moisture sensor data"
echo "   - Port 22 (SSH) from your IP"
echo ""

# 5. Test the deployment
echo "🧪 Testing the deployment..."
sleep 3

# Test health endpoint
echo "Testing health endpoint..."
if curl -s -X GET "http://$EC2_HOST:8080/health" | grep -q "healthy"; then
    echo "✅ Health check passed!"
else
    echo "❌ Health check failed!"
fi

# Display endpoints
echo ""
echo "✅ Moisture HTTP Server deployed successfully!"
echo ""
echo "📡 Endpoints:"
echo "   Health: http://$EC2_HOST:8080/health"
echo "   Moisture: http://$EC2_HOST:8080/api/sensor-data/moisture/munbon-m2m-moisture"
echo ""
echo "🔍 Monitor logs on EC2 with:"
echo "   ssh -i $PEM_FILE $EC2_USER@$EC2_HOST 'pm2 logs moisture-http'"
echo ""
echo "📊 Check status with:"
echo "   ssh -i $PEM_FILE $EC2_USER@$EC2_HOST 'pm2 status'"
echo ""
echo "🧪 Test moisture endpoint with:"
echo "curl -X POST http://$EC2_HOST:8080/api/sensor-data/moisture/munbon-m2m-moisture \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"gateway_id\":\"TEST-001\",\"sensor\":[{\"moisture\":45,\"temperature\":28}]}'"