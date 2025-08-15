import * as dotenv from 'dotenv';
import { SQSClient, ReceiveMessageCommand, DeleteMessageCommand } from '@aws-sdk/client-sqs';
import express from 'express';
import { createServer } from 'http';
import { Server } from 'socket.io';
import * as path from 'path';
import pino from 'pino';
import { TimescaleRepository } from '../../repository/timescale.repository';
import { processIncomingData } from '../../services/sqs-processor';

dotenv.config();

const logger = pino({
  transport: {
    target: 'pino-pretty',
    options: {
      colorize: true
    }
  }
});

// Configuration with defaults
const config = {
  SQS_QUEUE_URL: process.env.SQS_QUEUE_URL || '',
  AWS_REGION: process.env.AWS_REGION || 'ap-southeast-1',
  TIMESCALE_HOST: process.env.TIMESCALE_HOST || 'localhost',
  TIMESCALE_PORT: parseInt(process.env.TIMESCALE_PORT || '5433'),
  TIMESCALE_DB: process.env.TIMESCALE_DB || 'munbon_timescale',
  TIMESCALE_USER: process.env.TIMESCALE_USER || 'postgres',
  TIMESCALE_PASSWORD: process.env.TIMESCALE_PASSWORD || 'postgres',
  PORT: parseInt(process.env.CONSUMER_PORT || '3004'),
  MAX_RETRIES: 5,
  RETRY_DELAY: 5000,
  HEALTH_CHECK_INTERVAL: 30000
};

// Statistics tracking
interface ConsumerStats {
  messagesReceived: number;
  messagesProcessed: number;
  messagesFailed: number;
  lastMessageTime: string | null;
  startTime: string;
  sensorTypes: Record<string, number>;
  sensorIds: Set<string>;
  errors: { timestamp: string; error: string }[];
  isHealthy: boolean;
  lastHealthCheck: string;
}

const stats: ConsumerStats = {
  messagesReceived: 0,
  messagesProcessed: 0,
  messagesFailed: 0,
  lastMessageTime: null,
  startTime: new Date().toISOString(),
  sensorTypes: {},
  sensorIds: new Set(),
  errors: [],
  isHealthy: false,
  lastHealthCheck: new Date().toISOString()
};

// AWS SQS Configuration with retry logic
let sqsClient: SQSClient;
let isPolling = true;
let pollErrors = 0;
const MAX_POLL_ERRORS = 10;

// Initialize SQS client with proper error handling
function initializeSQSClient() {
  try {
    // Check if we have AWS credentials via environment or default
    const hasEnvCredentials = process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY;
    
    if (hasEnvCredentials) {
      logger.info('Using AWS credentials from environment variables');
      sqsClient = new SQSClient({
        region: config.AWS_REGION,
        credentials: {
          accessKeyId: process.env.AWS_ACCESS_KEY_ID!,
          secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY!
        }
      });
    } else {
      logger.info('Using AWS credentials from default chain (~/.aws/credentials or IAM role)');
      sqsClient = new SQSClient({
        region: config.AWS_REGION
      });
    }
  } catch (error) {
    logger.error({ error }, 'Failed to initialize SQS client');
    throw error;
  }
}

// Express app for dashboard
const app = express();
const server = createServer(app);
const io = new Server(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  }
});

// Recent telemetry data storage
const recentData: any[] = [];
const MAX_RECENT_DATA = 100;

// TimescaleDB repository
let timescaleRepo: TimescaleRepository;

// Process telemetry data
async function processTelemetryData(telemetryData: any): Promise<void> {
  const startTime = Date.now();
  
  try {
    logger.info({
      sensorType: telemetryData.sensorType,
      sensorId: telemetryData.sensorId,
      tokenGroup: telemetryData.tokenGroup
    }, '📡 New Telemetry Data');

    if (telemetryData.sensorType === 'water-level') {
      logger.info({
        waterLevel: `${telemetryData.data.level} cm`,
        voltage: `${(telemetryData.data.voltage / 100).toFixed(2)}V`,
        rssi: telemetryData.data.RSSI,
        location: {
          lat: telemetryData.data.latitude,
          lng: telemetryData.data.longitude
        }
      }, '💧 Water Level Data');
    }

    // Process the data using the imported function
    await processIncomingData(timescaleRepo, telemetryData, logger);

    // Update statistics
    stats.messagesProcessed++;
    stats.lastMessageTime = new Date().toISOString();
    stats.sensorTypes[telemetryData.sensorType] = (stats.sensorTypes[telemetryData.sensorType] || 0) + 1;
    stats.sensorIds.add(telemetryData.sensorId);

    // Store recent data
    recentData.unshift({
      ...telemetryData,
      processedAt: new Date().toISOString(),
      processingTime: Date.now() - startTime
    });
    if (recentData.length > MAX_RECENT_DATA) {
      recentData.pop();
    }

    // Emit to WebSocket
    io.emit('newData', telemetryData);

    logger.info({
      sensorType: telemetryData.sensorType,
      sensorId: telemetryData.sensorId
    }, 'Successfully processed sensor data');

  } catch (error) {
    logger.error({ error, telemetryData }, 'Failed to process telemetry data');
    stats.messagesFailed++;
    stats.errors.push({
      timestamp: new Date().toISOString(),
      error: error instanceof Error ? error.message : String(error)
    });
    if (stats.errors.length > 100) {
      stats.errors.shift(); // Keep only last 100 errors
    }
    throw error;
  }
}

// Poll SQS with robust error handling
async function pollSQS(): Promise<void> {
  const queueUrl = config.SQS_QUEUE_URL;
  
  if (!queueUrl) {
    logger.error('SQS_QUEUE_URL not configured');
    return;
  }
  
  try {
    const command = new ReceiveMessageCommand({
      QueueUrl: queueUrl,
      MaxNumberOfMessages: 10,
      WaitTimeSeconds: 20, // Long polling
      VisibilityTimeout: 300 // 5 minutes to process
    });
    
    const response = await sqsClient.send(command);
    
    // Reset error counter on successful poll
    pollErrors = 0;
    
    if (response.Messages && response.Messages.length > 0) {
      logger.info(`Received ${response.Messages.length} messages from SQS`);
      
      for (const message of response.Messages) {
        let messageProcessedSuccessfully = false;
        
        try {
          if (message.Body) {
            const telemetryData = JSON.parse(message.Body);
            
            // Update statistics
            stats.messagesReceived++;
            
            // Process the telemetry data
            await processTelemetryData(telemetryData);
            messageProcessedSuccessfully = true;
            
            // Delete message from queue after successful processing
            if (message.ReceiptHandle) {
              const deleteCommand = new DeleteMessageCommand({
                QueueUrl: queueUrl,
                ReceiptHandle: message.ReceiptHandle
              });
              
              await sqsClient.send(deleteCommand);
              logger.debug({ messageId: message.MessageId }, 'Deleted message from SQS');
            }
          }
        } catch (error) {
          logger.error({ error, messageId: message.MessageId }, 'Failed to process message');
          
          // If processing failed but we still want to remove from queue to prevent infinite retries
          if (!messageProcessedSuccessfully && message.ReceiptHandle) {
            try {
              const deleteCommand = new DeleteMessageCommand({
                QueueUrl: queueUrl,
                ReceiptHandle: message.ReceiptHandle
              });
              
              await sqsClient.send(deleteCommand);
              logger.warn({ 
                messageId: message.MessageId 
              }, 'Deleted failed message from SQS to prevent infinite retries');
            } catch (deleteError) {
              logger.error({ 
                error: deleteError, 
                messageId: message.MessageId 
              }, 'Failed to delete message from SQS');
            }
          }
        }
      }
    }
  } catch (error: any) {
    pollErrors++;
    logger.error({ 
      error: error.message || error,
      pollErrors,
      maxErrors: MAX_POLL_ERRORS 
    }, 'Error polling SQS');
    
    // If too many consecutive errors, pause polling
    if (pollErrors >= MAX_POLL_ERRORS) {
      logger.error('Too many consecutive poll errors, pausing for 60 seconds');
      await new Promise(resolve => setTimeout(resolve, 60000));
      pollErrors = 0; // Reset counter after pause
    }
  }
}

// Continuous polling with error recovery
async function startPolling(): Promise<void> {
  logger.info('🚀 Starting SQS consumer...');
  
  while (isPolling) {
    try {
      await pollSQS();
      // Small delay between polls
      await new Promise(resolve => setTimeout(resolve, 100));
    } catch (error) {
      logger.error({ error }, 'Unexpected error in polling loop');
      // Wait before retrying
      await new Promise(resolve => setTimeout(resolve, config.RETRY_DELAY));
    }
  }
  
  logger.info('Polling stopped');
}

// Health check
async function performHealthCheck(): Promise<void> {
  try {
    // Check database connection
    await timescaleRepo.query('SELECT 1');
    
    // Check SQS access (lightweight check)
    const testCommand = new ReceiveMessageCommand({
      QueueUrl: config.SQS_QUEUE_URL,
      MaxNumberOfMessages: 1,
      WaitTimeSeconds: 0,
      VisibilityTimeout: 1
    });
    await sqsClient.send(testCommand);
    
    stats.isHealthy = true;
    stats.lastHealthCheck = new Date().toISOString();
  } catch (error) {
    stats.isHealthy = false;
    stats.lastHealthCheck = new Date().toISOString();
    logger.error({ error }, 'Health check failed');
  }
}

// Dashboard routes
app.use(express.static(path.join(__dirname, '../../../public')));

app.get('/health', async (_req, res) => {
  await performHealthCheck();
  res.status(stats.isHealthy ? 200 : 503).json({
    status: stats.isHealthy ? 'healthy' : 'unhealthy',
    uptime: Date.now() - new Date(stats.startTime).getTime(),
    lastHealthCheck: stats.lastHealthCheck
  });
});

app.get('/api/stats', (_req, res) => {
  res.json({
    ...stats,
    sensorCount: stats.sensorIds.size,
    uptime: Date.now() - new Date(stats.startTime).getTime()
  });
});

app.get('/api/recent', (req, res) => {
  const limit = parseInt(req.query.limit as string) || 20;
  res.json(recentData.slice(0, limit));
});

// Main startup with retry logic
async function start(): Promise<void> {
  let retries = 0;
  
  while (retries < config.MAX_RETRIES) {
    try {
      // Initialize AWS SQS client
      initializeSQSClient();
      
      // Initialize TimescaleDB connection
      timescaleRepo = new TimescaleRepository({
        host: config.TIMESCALE_HOST,
        port: config.TIMESCALE_PORT,
        database: config.TIMESCALE_DB,
        user: config.TIMESCALE_USER,
        password: config.TIMESCALE_PASSWORD
      });

      await timescaleRepo.initialize();
      logger.info('✅ Connected to TimescaleDB');

      // Start health check interval
      setInterval(performHealthCheck, config.HEALTH_CHECK_INTERVAL);

      // Start HTTP server
      server.listen(config.PORT, () => {
        logger.info(`📊 Dashboard running at http://localhost:${config.PORT}`);
        logger.info('🔄 Starting SQS polling...');
        
        // Start polling in background with error recovery
        startPolling().catch(error => {
          logger.error({ error }, 'Fatal error in polling - will retry');
          // Don't exit, let the polling loop handle retries
        });
      });

      // If we get here, startup was successful
      stats.isHealthy = true;
      break;
      
    } catch (error) {
      retries++;
      logger.error({ 
        error, 
        retries, 
        maxRetries: config.MAX_RETRIES 
      }, 'Failed to start consumer, retrying...');
      
      if (retries >= config.MAX_RETRIES) {
        logger.error('Max retries exceeded, exiting');
        process.exit(1);
      }
      
      await new Promise(resolve => setTimeout(resolve, config.RETRY_DELAY));
    }
  }
}

// Graceful shutdown
process.on('SIGTERM', async () => {
  logger.info('SIGTERM received, shutting down gracefully...');
  isPolling = false;
  
  // Give some time for current operations to complete
  setTimeout(() => {
    server.close(() => {
      logger.info('Server closed');
      process.exit(0);
    });
  }, 5000);
});

process.on('SIGINT', async () => {
  logger.info('SIGINT received, shutting down gracefully...');
  isPolling = false;
  
  setTimeout(() => {
    server.close(() => {
      logger.info('Server closed');
      process.exit(0);
    });
  }, 5000);
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  logger.error({ error }, 'Uncaught exception');
  stats.errors.push({
    timestamp: new Date().toISOString(),
    error: error.message
  });
});

process.on('unhandledRejection', (reason, promise) => {
  logger.error({ reason, promise }, 'Unhandled rejection');
  stats.errors.push({
    timestamp: new Date().toISOString(),
    error: String(reason)
  });
});

// Start the consumer
start();