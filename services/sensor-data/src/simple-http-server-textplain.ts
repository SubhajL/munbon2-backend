import express from 'express';
import { SQSClient, SendMessageCommand } from '@aws-sdk/client-sqs';
import * as dotenv from 'dotenv';
import pino from 'pino';

dotenv.config();

const app = express();

// Add raw text parser for text/plain content type
app.use(express.text({ type: 'text/plain' }));
// Keep JSON parser for backward compatibility
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

// Simple HTTP endpoint for moisture data - handles both text/plain and application/json
app.post('/api/sensor-data/moisture/:token', async (req, res) => {
  try {
    const { token } = req.params;
    const contentType = req.headers['content-type'];
    let data: any;
    
    // Handle different content types
    if (contentType?.includes('text/plain')) {
      // Parse text body as JSON
      try {
        // If body is a string, try to parse it
        if (typeof req.body === 'string') {
          data = JSON.parse(req.body);
        } else {
          data = req.body;
        }
      } catch (parseError) {
        logger.error({ parseError, body: req.body }, 'Failed to parse text/plain body as JSON');
        res.status(400).json({ 
          status: 'error', 
          message: 'Invalid JSON in request body',
          hint: 'Send raw JSON without quotes: {"gw_id":"0003",...}'
        });
        return;
      }
    } else {
      // For application/json or other types, use body as-is
      data = req.body;
    }
    
    logger.info({ 
      token, 
      contentType,
      dataType: typeof data,
      data 
    }, 'Received moisture data via HTTP');
    
    // Validate data has required fields
    if (!data || typeof data !== 'object') {
      res.status(400).json({ 
        status: 'error', 
        message: 'Invalid data format',
        hint: 'Expected JSON object' 
      });
      return;
    }
    
    // Prepare message for SQS
    const message = {
      timestamp: new Date().toISOString(),
      token: token,
      tokenGroup: 'moisture-munbon',
      sensorType: 'moisture',
      sensorId: data.gw_id || data.gateway_id,
      location: { 
        lat: parseFloat(data.gps_lat || data.latitude) || 0, 
        lng: parseFloat(data.gps_lng || data.longitude) || 0 
      },
      data: data,
      sourceIp: req.ip,
      metadata: {
        contentType: contentType
      }
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
      sensorCount: data.sensor?.length || 0
    }, 'Sent to SQS successfully');
    
    res.status(200).json({ status: 'success', message: 'Data received and processed' });
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
  logger.info(`🚀 HTTP server (with text/plain support) listening on port ${PORT}`);
  logger.info(`📡 Moisture endpoint: http://43.209.22.250:${PORT}/api/sensor-data/moisture/munbon-m2m-moisture`);
  logger.info(`✅ Accepts both Content-Type: text/plain and application/json`);
});