#!/bin/bash

# Deployment script for simple HTTP server on EC2
# Run this script on your EC2 instance

set -e

echo "🚀 Starting deployment of Simple HTTP Server for Legacy Moisture Sensors"

# 1. Update security group to allow port 8080
echo "📋 Please ensure your EC2 security group allows:"
echo "   - Port 8080 (HTTP) from 0.0.0.0/0"
echo "   - Port 3003 (Sensor service) from 0.0.0.0/0"
echo "   - Port 22 (SSH) from your IP"
echo ""
echo "Press Enter when security group is configured..."
read

# 2. Navigate to project directory
cd ~/munbon2-backend/services/sensor-data || {
    echo "❌ Project directory not found. Creating it..."
    mkdir -p ~/munbon2-backend/services/sensor-data
    cd ~/munbon2-backend/services/sensor-data
}

# 3. Create the simple HTTP server file
echo "📝 Creating simple-http-server.ts..."
cat > src/simple-http-server.ts << 'EOF'
import express from 'express';
import { SQSClient, SendMessageCommand } from '@aws-sdk/client-sqs';
import * as dotenv from 'dotenv';
import pino from 'pino';

dotenv.config();

const app = express();
app.use(express.json());

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
      sensorId: data.gateway_id,
      location: { lat: 0, lng: 0 }, // Update if location provided
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
    
    logger.info({ token, gateway_id: data.gateway_id }, 'Sent to SQS successfully');
    
    res.status(200).json({ status: 'success', message: 'Data received' });
  } catch (error) {
    logger.error({ error }, 'Failed to process moisture data');
    res.status(500).json({ status: 'error', message: 'Internal server error' });
  }
});

// Health check
app.get('/health', (req, res) => {
  res.status(200).send('OK');
});

const PORT = process.env.HTTP_PORT || 8080;

app.listen(PORT, '0.0.0.0', () => {
  logger.info(`🚀 Simple HTTP server listening on port ${PORT}`);
  logger.info(`📡 Moisture endpoint: http://$(curl -s http://169.254.169.254/latest/meta-data/public-hostname):${PORT}/api/sensor-data/moisture/munbon-m2m-moisture`);
});
EOF

# 4. Install dependencies
echo "📦 Installing dependencies..."
npm install express @aws-sdk/client-sqs pino pino-pretty
npm install -D @types/express typescript ts-node

# 5. Create PM2 ecosystem file for HTTP server
echo "⚙️ Creating PM2 configuration..."
cat > ecosystem.http.config.js << 'EOF'
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
EOF

# 6. Create logs directory
mkdir -p logs

# 7. Stop existing instance if running
echo "🛑 Stopping any existing moisture-http process..."
pm2 stop moisture-http 2>/dev/null || true
pm2 delete moisture-http 2>/dev/null || true

# 8. Start with PM2
echo "🚀 Starting HTTP server with PM2..."
pm2 start ecosystem.http.config.js

# 9. Save PM2 configuration
pm2 save

# 10. Show status
pm2 status moisture-http

# 11. Get public endpoint
PUBLIC_DNS=$(curl -s http://169.254.169.254/latest/meta-data/public-hostname)
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📡 Your moisture sensor HTTP endpoints:"
echo "   Using hostname: http://${PUBLIC_DNS}:8080/api/sensor-data/moisture/munbon-m2m-moisture"
echo "   Using IP: http://${PUBLIC_IP}:8080/api/sensor-data/moisture/munbon-m2m-moisture"
echo ""
echo "🔍 Check logs with: pm2 logs moisture-http"
echo "📊 Monitor with: pm2 monit"
echo ""
echo "🧪 Test with:"
echo "curl -X POST http://${PUBLIC_DNS}:8080/api/sensor-data/moisture/munbon-m2m-moisture \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"gateway_id\":\"TEST-001\",\"sensor\":[{\"moisture\":45,\"temperature\":28}]}'"