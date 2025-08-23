import * as AWS from 'aws-sdk';
import { ShapeFileService } from '../services/shapefile.service';
import { logger } from '../utils/logger';
import { connectDatabase } from '../config/database';

export class ShapeFileQueueProcessor {
  private sqs: AWS.SQS;
  private shapeFileService: ShapeFileService;
  private isRunning: boolean = false;
  private queueUrl: string;

  constructor() {
    AWS.config.update({ region: process.env.AWS_REGION || 'ap-southeast-1' });
    this.sqs = new AWS.SQS();
    this.shapeFileService = new ShapeFileService();
    
    this.queueUrl = process.env.GIS_SQS_QUEUE_URL || 
      `https://sqs.${process.env.AWS_REGION}.amazonaws.com/${process.env.AWS_ACCOUNT_ID}/munbon-gis-shapefile-queue`;
  }

  async start() {
    if (this.isRunning) {
      logger.warn('Queue processor is already running');
      return;
    }

    this.isRunning = true;
    logger.info('Starting shape file queue processor...', {
      queueUrl: this.queueUrl,
      region: process.env.AWS_REGION
    });

    // Connect to database
    try {
      await connectDatabase();
      logger.info('Database connected successfully');
    } catch (dbError) {
      logger.error('Failed to connect to database', {
        error: dbError instanceof Error ? dbError.message : dbError,
        stack: dbError instanceof Error ? dbError.stack : undefined
      });
      throw dbError;
    }

    // Start polling
    logger.info('Starting message polling');
    this.pollQueue();
  }

  async stop() {
    logger.info('Stopping shape file queue processor...');
    this.isRunning = false;
  }

  private async pollQueue() {
    logger.info('Starting queue polling', { queueUrl: this.queueUrl });
    
    while (this.isRunning) {
      try {
        logger.debug('Polling for messages...');
        const { Messages } = await this.sqs.receiveMessage({
          QueueUrl: this.queueUrl,
          MaxNumberOfMessages: 1,
          WaitTimeSeconds: 20, // Long polling
          VisibilityTimeout: 300, // 5 minutes to process
        }).promise();

        if (Messages && Messages.length > 0) {
          logger.info('Received messages', { count: Messages.length });
          for (const message of Messages) {
            await this.processMessage(message);
          }
        } else {
          logger.debug('No messages received');
        }
      } catch (error) {
        logger.error(`Error polling SQS queue: ${error instanceof Error ? error.message : String(error)}`);
        // Wait before retrying
        await new Promise(resolve => setTimeout(resolve, 5000));
      }
    }
  }

  private async processMessage(message: AWS.SQS.Message) {
    const startTime = Date.now();
    
    try {
      if (!message.Body) {
        throw new Error('Empty message body');
      }

      const messageData = JSON.parse(message.Body);
      logger.info(`Processing shape file message - Upload ID: ${messageData.uploadId}, File: ${messageData.fileName}`);

      // Process the shape file
      try {
        await this.shapeFileService.processShapeFileFromQueue(messageData);
      } catch (innerError) {
        logger.error('Service processing error', {
          error: innerError instanceof Error ? innerError.message : innerError,
          stack: innerError instanceof Error ? innerError.stack : undefined
        });
        throw innerError;
      }

      // Delete message from queue on success
      if (message.ReceiptHandle) {
        await this.sqs.deleteMessage({
          QueueUrl: this.queueUrl,
          ReceiptHandle: message.ReceiptHandle,
        }).promise();
      }

      const processingTime = Date.now() - startTime;
      logger.info(`Shape file processed successfully - Upload ID: ${messageData.uploadId}, Time: ${processingTime}ms`);

    } catch (error) {
      logger.error(`Failed to process shape file message - Message ID: ${message.MessageId}, Time: ${Date.now() - startTime}ms, Error: ${error instanceof Error ? error.message : String(error)}`);
      
      // Message will return to queue after visibility timeout
      // and eventually go to DLQ after max retries
    }
  }
}

// If running as standalone worker
if (require.main === module) {
  const processor = new ShapeFileQueueProcessor();

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

  // Start the processor
  processor.start().catch(error => {
    logger.error(`Failed to start queue processor: ${error instanceof Error ? error.message : String(error)}`);
    process.exit(1);
  });
}