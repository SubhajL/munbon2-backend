#!/usr/bin/env ts-node

import * as dotenv from 'dotenv';
import { 
  SQSClient, 
  ReceiveMessageCommand, 
  SendMessageCommand, 
  DeleteMessageCommand 
} from '@aws-sdk/client-sqs';
import pino from 'pino';

dotenv.config();

const logger = pino({
  transport: {
    target: 'pino-pretty',
    options: {
      colorize: true
    }
  }
});

const sqsClient = new SQSClient({
  region: process.env.AWS_REGION || 'ap-southeast-1'
});

const DLQ_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-dlq';
const MAIN_QUEUE_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';

async function reprocessDLQMessages() {
  let totalProcessed = 0;
  let hasMoreMessages = true;

  logger.info('Starting DLQ reprocessing...');

  while (hasMoreMessages) {
    try {
      // Receive messages from DLQ
      const receiveCommand = new ReceiveMessageCommand({
        QueueUrl: DLQ_URL,
        MaxNumberOfMessages: 10,
        WaitTimeSeconds: 5
      });

      const response = await sqsClient.send(receiveCommand);

      if (!response.Messages || response.Messages.length === 0) {
        hasMoreMessages = false;
        logger.info('No more messages in DLQ');
        break;
      }

      logger.info(`Processing ${response.Messages.length} messages from DLQ`);

      // Process each message
      for (const message of response.Messages) {
        try {
          if (message.Body) {
            // Send message to main queue
            const sendCommand = new SendMessageCommand({
              QueueUrl: MAIN_QUEUE_URL,
              MessageBody: message.Body,
              MessageAttributes: message.MessageAttributes
            });

            await sqsClient.send(sendCommand);

            // Delete from DLQ after successful send
            if (message.ReceiptHandle) {
              const deleteCommand = new DeleteMessageCommand({
                QueueUrl: DLQ_URL,
                ReceiptHandle: message.ReceiptHandle
              });

              await sqsClient.send(deleteCommand);
              totalProcessed++;
              
              // Log sample data for verification
              if (totalProcessed <= 5) {
                const data = JSON.parse(message.Body);
                logger.info({
                  messageNumber: totalProcessed,
                  sensorId: data.sensorId,
                  sensorType: data.sensorType,
                  timestamp: data.timestamp
                }, 'Sample message reprocessed');
              }
            }
          }
        } catch (error) {
          logger.error({ error, messageId: message.MessageId }, 'Failed to reprocess individual message');
        }
      }

      logger.info(`Progress: ${totalProcessed} messages reprocessed`);
    } catch (error) {
      logger.error({ error }, 'Error in reprocessing loop');
      break;
    }
  }

  logger.info(`✅ DLQ reprocessing complete. Total messages moved: ${totalProcessed}`);
}

// Run the reprocessing
reprocessDLQMessages().catch(error => {
  logger.error({ error }, 'Fatal error in DLQ reprocessing');
  process.exit(1);
});