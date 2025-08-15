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
      sensorId: data.gw_id || data.gateway_id,
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
    
    logger.info({ token, gateway_id: data.gateway_id }, 'Sent to SQS successfully');
    
    res.status(200).json({ status: 'success', message: 'Data received' });
  } catch (error) {
    logger.error({ error }, 'Failed to process moisture data');
    res.status(500).json({ status: 'error', message: 'Internal server error' });
  }
});

// Health check
app.get('/health', (_req, res) => {
  res.status(200).send('OK');
});

const PORT = parseInt(process.env.HTTP_PORT || '8080');

app.listen(PORT, '0.0.0.0', () => {
  logger.info(`🚀 Simple HTTP server listening on port ${PORT}`);
  logger.info(`📡 Moisture endpoint: http://ec2-43.209.22.250.ap-southeast-7.compute.amazonaws.com:${PORT}/api/sensor-data/moisture/munbon-m2m-moisture`);
});