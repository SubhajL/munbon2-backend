#!/usr/bin/env ts-node

import * as dotenv from 'dotenv';
import { SQSClient, SendMessageCommand } from '@aws-sdk/client-sqs';
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

const QUEUE_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';

// Test water level message with MAC address
const testMessage = {
  timestamp: new Date().toISOString(),
  token: 'munbon-ridr-water-level',
  tokenGroup: 'water-level-munbon',
  sensorType: 'water-level',
  sensorId: '222410831182181',  // This will be ignored in favor of MAC-based ID
  location: {
    lat: 14.00268,
    lng: 100.62698
  },
  data: {
    deviceId: '222410831182181',
    voltage: 389,
    level: -15,  // Changed to -15 to distinguish from existing data
    macAddress: 'AABBCCDDEEFF',  // MAC address - should result in AWD-EEFF
    latitude: 14.00268,
    longitude: 100.62698,
    RSSI: -30,
    timestamp: Math.floor(Date.now() / 1000)
  },
  sourceIp: '127.0.0.1',
  metadata: {
    manufacturer: 'RID-R',
    battery: 389,
    rssi: -30,
    macAddress: 'AABBCCDDEEFF'
  }
};

async function sendTestMessage() {
  try {
    const command = new SendMessageCommand({
      QueueUrl: QUEUE_URL,
      MessageBody: JSON.stringify(testMessage)
    });

    const response = await sqsClient.send(command);
    
    logger.info({
      messageId: response.MessageId,
      expectedSensorId: 'AWD-EEFF',
      macAddress: testMessage.data.macAddress,
      level: testMessage.data.level
    }, 'Test message sent successfully');

    logger.info('Check the dashboard at http://localhost:3004 to see if sensor ID appears as AWD-EEFF');
  } catch (error) {
    logger.error({ error }, 'Failed to send test message');
  }
}

sendTestMessage();