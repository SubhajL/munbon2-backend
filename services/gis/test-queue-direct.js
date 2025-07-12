require('dotenv').config();
const AWS = require('aws-sdk');

AWS.config.update({ region: process.env.AWS_REGION || 'ap-southeast-1' });
const sqs = new AWS.SQS();

const queueUrl = process.env.GIS_SQS_QUEUE_URL || 
  `https://sqs.${process.env.AWS_REGION}.amazonaws.com/${process.env.AWS_ACCOUNT_ID}/munbon-gis-shapefile-queue`;

console.log('Using queue URL:', queueUrl);
console.log('AWS Region:', process.env.AWS_REGION);
console.log('AWS Account ID:', process.env.AWS_ACCOUNT_ID);

async function testQueue() {
  try {
    // Get queue attributes
    const attrs = await sqs.getQueueAttributes({
      QueueUrl: queueUrl,
      AttributeNames: ['All']
    }).promise();
    
    console.log('\nQueue Attributes:');
    console.log('Messages Available:', attrs.Attributes.ApproximateNumberOfMessages);
    console.log('Messages In Flight:', attrs.Attributes.ApproximateNumberOfMessagesNotVisible);
    
    // Try to receive a message
    console.log('\nTrying to receive message...');
    const result = await sqs.receiveMessage({
      QueueUrl: queueUrl,
      MaxNumberOfMessages: 1,
      WaitTimeSeconds: 5
    }).promise();
    
    if (result.Messages && result.Messages.length > 0) {
      console.log('\nReceived message:');
      console.log(JSON.stringify(JSON.parse(result.Messages[0].Body), null, 2));
    } else {
      console.log('\nNo messages available');
    }
    
  } catch (error) {
    console.error('\nError:', error.message);
    console.error('Stack:', error.stack);
  }
}

testQueue();