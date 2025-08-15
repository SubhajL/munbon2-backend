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

// Track empty payload sources for monitoring
const emptyPayloadTracker = new Map<string, { count: number; lastSeen: Date }>();

// Simple HTTP endpoint for moisture data
app.post('/api/sensor-data/moisture/:token', async (req, res) => {
  try {
    const { token } = req.params;
    const data = req.body;
    const sourceIp = req.ip || req.connection.remoteAddress || 'unknown';
    
    // Check if data is empty or missing gateway ID
    const isEmptyPayload = !data || Object.keys(data).length === 0;
    const gatewayId = data?.gw_id || data?.gateway_id;
    const hasNoGatewayId = !gatewayId;
    
    if (isEmptyPayload || hasNoGatewayId) {
      // Track empty/invalid payloads for monitoring
      const tracker = emptyPayloadTracker.get(sourceIp) || { count: 0, lastSeen: new Date() };
      tracker.count++;
      tracker.lastSeen = new Date();
      emptyPayloadTracker.set(sourceIp, tracker);
      
      logger.info({ 
        token, 
        sourceIp, 
        emptyPayloadCount: tracker.count,
        isEmptyPayload,
        hasNoGatewayId,
        message: 'Received empty/invalid moisture data - accepting but not forwarding to SQS' 
      });
      
      // Return success but don't send to SQS (won't be written to database)
      return res.status(200).json({ 
        status: 'success', 
        message: 'Data received (empty payload acknowledged)' 
      });
    }
    
    // Valid data - process normally
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
    
    res.status(200).json({ status: 'success', message: 'Data received and processed' });
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
    sources: stats.sort((a, b) => b.count - a.count),
    note: 'Empty payloads are accepted but not written to database'
  });
});

const PORT = parseInt(process.env.HTTP_PORT || '8080');

app.listen(PORT, '0.0.0.0', () => {
  logger.info(`🚀 Simple HTTP server listening on port ${PORT}`);
  logger.info(`📡 Moisture endpoint: http://ec2-43.209.22.250.ap-southeast-7.compute.amazonaws.com:${PORT}/api/sensor-data/moisture/munbon-m2m-moisture`);
  logger.info(`📊 Empty payload stats: http://localhost:${PORT}/api/stats/empty-payloads`);
  logger.info(`✅ Empty payloads are accepted (200 OK) but not forwarded to SQS/database`);
  
  // Log empty payload stats every 5 minutes
  setInterval(() => {
    if (emptyPayloadTracker.size > 0) {
      logger.info({
        emptyPayloadSources: emptyPayloadTracker.size,
        totalEmptyPayloads: Array.from(emptyPayloadTracker.values()).reduce((sum, v) => sum + v.count, 0)
      }, 'Empty payload statistics (accepted but not stored)');
    }
  }, 5 * 60 * 1000);
});