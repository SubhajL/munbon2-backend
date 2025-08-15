import { SQSClient, ReceiveMessageCommand, DeleteMessageCommand } from '@aws-sdk/client-sqs';
import * as dotenv from 'dotenv';
import pino from 'pino';

dotenv.config();

const logger = pino({
  level: 'debug',
  transport: {
    target: 'pino-pretty',
    options: { colorize: true }
  }
});

const sqsClient = new SQSClient({
  region: process.env.AWS_REGION || 'ap-southeast-1'
});

const SQS_QUEUE_URL = process.env.SQS_QUEUE_URL || 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';

async function processMessages() {
  logger.info('Starting debug consumer for water level messages...');
  
  while (true) {
    try {
      const response = await sqsClient.send(new ReceiveMessageCommand({
        QueueUrl: SQS_QUEUE_URL,
        MaxNumberOfMessages: 10,
        WaitTimeSeconds: 20,
        VisibilityTimeout: 30
      }));
      
      if (response.Messages && response.Messages.length > 0) {
        for (const message of response.Messages) {
          const body = JSON.parse(message.Body || '{}');
          
          if (body.sensorType === 'water-level') {
            logger.info('🌊 Found water level message!');
            logger.info({ 
              messageId: message.MessageId,
              body: JSON.stringify(body, null, 2)
            }, 'Water level message details');
            
            // Check data structure
            logger.debug({ 
              hasData: !!body.data,
              dataKeys: body.data ? Object.keys(body.data) : [],
              hasMacAddress: !!(body.data?.macAddress || body.data?.mac_address || body.data?.MAC),
              sensorId: body.sensorId,
              formattedId: body.data?.formattedSensorId
            }, 'Water level data structure');
            
            // Delete message to prevent reprocessing
            await sqsClient.send(new DeleteMessageCommand({
              QueueUrl: SQS_QUEUE_URL,
              ReceiptHandle: message.ReceiptHandle
            }));
            
            logger.info('✅ Deleted water level message from queue');
          }
        }
      }
    } catch (error) {
      logger.error({ error }, 'Error processing messages');
    }
    
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
}

processMessages().catch(console.error);