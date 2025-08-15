import { SQSClient, SendMessageCommand } from '@aws-sdk/client-sqs';
import * as dotenv from 'dotenv';

dotenv.config();

const sqsClient = new SQSClient({
  region: process.env.AWS_REGION || 'ap-southeast-1'
});

const SQS_QUEUE_URL = process.env.SQS_QUEUE_URL || 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';

async function sendTestMessage() {
  // Simulate the Lambda water level message structure
  const message = {
    timestamp: new Date().toISOString(),
    token: 'water-level-munbon',
    tokenGroup: 'water-level-munbon',
    sensorType: 'water-level',
    sensorId: 'AWD-0001',
    location: { lat: 17.123, lng: 103.456 },
    data: {
      deviceID: 'AWD-0001',
      macAddress: 'AA:BB:CC:DD:00:01',
      latitude: 17.123,
      longitude: 103.456,
      RSSI: -65,
      voltage: 385,  // Voltage in centivolts (3.85V)
      level: 245.5,  // Water level in cm
      timestamp: Date.now()
    },
    sourceIp: '127.0.0.1',
    metadata: {
      source: 'test-script'
    }
  };
  
  console.log('Sending water level test message:', JSON.stringify(message, null, 2));
  
  const command = new SendMessageCommand({
    QueueUrl: SQS_QUEUE_URL,
    MessageBody: JSON.stringify(message)
  });
  
  const result = await sqsClient.send(command);
  console.log('Message sent successfully:', result.MessageId);
}

sendTestMessage().catch(console.error);