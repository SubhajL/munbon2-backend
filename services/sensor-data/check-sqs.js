const { SQSClient, GetQueueAttributesCommand, ReceiveMessageCommand } = require('@aws-sdk/client-sqs');
require('dotenv').config();

const client = new SQSClient({
  region: process.env.AWS_REGION || 'ap-southeast-1',
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
  },
});

async function checkSQS() {
  console.log('Checking SQS Queue...\n');
  console.log('Queue URL:', process.env.SQS_QUEUE_URL);
  
  try {
    // Get queue attributes
    const attributesCommand = new GetQueueAttributesCommand({
      QueueUrl: process.env.SQS_QUEUE_URL,
      AttributeNames: [
        'ApproximateNumberOfMessages',
        'ApproximateNumberOfMessagesNotVisible',
        'ApproximateNumberOfMessagesDelayed',
      ],
    });
    
    const attributes = await client.send(attributesCommand);
    console.log('\nQueue Status:');
    console.log('- Messages Available:', attributes.Attributes.ApproximateNumberOfMessages);
    console.log('- Messages In Flight:', attributes.Attributes.ApproximateNumberOfMessagesNotVisible);
    console.log('- Messages Delayed:', attributes.Attributes.ApproximateNumberOfMessagesDelayed);
    
    // Try to peek at messages without deleting
    if (parseInt(attributes.Attributes.ApproximateNumberOfMessages) > 0) {
      console.log('\nPeeking at messages (without deleting):');
      const receiveCommand = new ReceiveMessageCommand({
        QueueUrl: process.env.SQS_QUEUE_URL,
        MaxNumberOfMessages: 5,
        VisibilityTimeout: 0, // Don't hide messages
      });
      
      const messages = await client.send(receiveCommand);
      if (messages.Messages && messages.Messages.length > 0) {
        messages.Messages.forEach((msg, index) => {
          console.log(`\nMessage ${index + 1}:`);
          try {
            const body = JSON.parse(msg.Body);
            console.log('- Type:', body.sensor_type || 'Unknown');
            console.log('- Device ID:', body.deviceID || body.gateway_id || 'Unknown');
            console.log('- Timestamp:', new Date(body.timestamp || Date.now()).toISOString());
          } catch (e) {
            console.log('- Raw Body:', msg.Body);
          }
        });
      }
    } else {
      console.log('\nNo messages in queue.');
    }
    
  } catch (error) {
    console.error('Error checking SQS:', error.message);
  }
}

checkSQS();