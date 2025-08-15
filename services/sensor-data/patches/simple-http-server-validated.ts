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

// Track empty payload sources
const emptyPayloadTracker = new Map<string, { count: number; lastSeen: Date }>();

// Simple HTTP endpoint for moisture data
app.post('/api/sensor-data/moisture/:token', async (req, res) => {
  try {
    const { token } = req.params;
    const data = req.body;
    const sourceIp = req.ip || req.connection.remoteAddress || 'unknown';
    
    // Validate incoming data
    if (!data || Object.keys(data).length === 0) {
      // Track empty payloads
      const tracker = emptyPayloadTracker.get(sourceIp) || { count: 0, lastSeen: new Date() };
      tracker.count++;
      tracker.lastSeen = new Date();
      emptyPayloadTracker.set(sourceIp, tracker);
      
      logger.warn({ 
        token, 
        sourceIp, 
        emptyPayloadCount: tracker.count,
        message: 'Rejected empty moisture data payload' 
      });
      
      return res.status(400).json({ 
        status: 'error', 
        message: 'Empty data payload not allowed' 
      });
    }
    
    // Validate required fields
    const gatewayId = data.gw_id || data.gateway_id;
    if (!gatewayId) {
      logger.warn({ 
        token, 
        sourceIp, 
        data,
        message: 'Rejected moisture data without gateway ID' 
      });
      
      return res.status(400).json({ 
        status: 'error', 
        message: 'Gateway ID (gw_id or gateway_id) is required' 
      });
    }
    
    logger.info({ token, data, sourceIp }, 'Received valid moisture data via HTTP');
    
    // Prepare message for SQS
    const message = {
      timestamp: new Date().toISOString(),
      token: token,
      tokenGroup: 'moisture-munbon',
      sensorType: 'moisture',
      sensorId: gatewayId,
      location: { lat: 0, lng: 0 }, // Update if location provided
      data: data,
      sourceIp: sourceIp,
      metadata: {}
    };
    
    // Send to SQS
    const command = new SendMessageCommand({
      QueueUrl: SQS_QUEUE_URL,
      MessageBody: JSON.stringify(message)
    });
    
    await sqsClient.send(command);
    
    logger.info({ token, gateway_id: gatewayId }, 'Sent to SQS successfully');
    
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

// Empty payload statistics endpoint
app.get('/api/stats/empty-payloads', (req, res) => {
  const stats = Array.from(emptyPayloadTracker.entries()).map(([ip, data]) => ({
    ip,
    count: data.count,
    lastSeen: data.lastSeen
  }));
  
  res.json({
    totalSources: stats.length,
    sources: stats.sort((a, b) => b.count - a.count)
  });
});

const PORT = parseInt(process.env.HTTP_PORT || '8080');

app.listen(PORT, '0.0.0.0', () => {
  logger.info(`🚀 Simple HTTP server listening on port ${PORT}`);
  logger.info(`📡 Moisture endpoint: http://ec2-43.209.22.250.ap-southeast-7.compute.amazonaws.com:${PORT}/api/sensor-data/moisture/munbon-m2m-moisture`);
  logger.info(`📊 Empty payload stats: http://localhost:${PORT}/api/stats/empty-payloads`);
  
  // Log empty payload stats every 5 minutes
  setInterval(() => {
    if (emptyPayloadTracker.size > 0) {
      logger.info({
        emptyPayloadSources: emptyPayloadTracker.size,
        totalEmptyPayloads: Array.from(emptyPayloadTracker.values()).reduce((sum, v) => sum + v.count, 0)
      }, 'Empty payload statistics');
    }
  }, 5 * 60 * 1000);
});