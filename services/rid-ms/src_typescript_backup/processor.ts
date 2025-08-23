import { ShapeFileProcessor } from './processors/shape-file-processor';
import pino from 'pino';

const logger = pino({ level: process.env.LOG_LEVEL || 'info' });

async function main() {
  logger.info('Starting RID-MS Shape File Processing Service...');

  // Validate required environment variables
  const requiredEnvVars = [
    'DATABASE_URL',
    'AWS_REGION',
    'SQS_QUEUE_URL',
    'SHAPE_FILE_BUCKET'
  ];

  for (const envVar of requiredEnvVars) {
    if (!process.env[envVar]) {
      logger.error(`Missing required environment variable: ${envVar}`);
      process.exit(1);
    }
  }

  const processor = new ShapeFileProcessor();

  // Handle graceful shutdown
  process.on('SIGTERM', async () => {
    logger.info('SIGTERM received, shutting down gracefully...');
    await processor.stop();
    process.exit(0);
  });

  process.on('SIGINT', async () => {
    logger.info('SIGINT received, shutting down gracefully...');
    await processor.stop();
    process.exit(0);
  });

  process.on('unhandledRejection', (reason, promise) => {
    logger.error({ reason, promise }, 'Unhandled Rejection');
  });

  process.on('uncaughtException', (error) => {
    logger.error({ error }, 'Uncaught Exception');
    process.exit(1);
  });

  try {
    await processor.start();
  } catch (error) {
    logger.error({ error }, 'Failed to start processor');
    process.exit(1);
  }
}

// Start the processor
main().catch((error) => {
  logger.error({ error }, 'Unhandled error in main');
  process.exit(1);
});