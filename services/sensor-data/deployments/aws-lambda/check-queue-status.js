const AWS = require('aws-sdk');

AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();

async function checkQueues() {
  const dlqUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-dlq';
  const mainQueueUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';
  
  const dlqAttrs = await sqs.getQueueAttributes({
    QueueUrl: dlqUrl,
    AttributeNames: ['All']
  }).promise();
  
  const mainAttrs = await sqs.getQueueAttributes({
    QueueUrl: mainQueueUrl,
    AttributeNames: ['All']
  }).promise();
  
  console.log('=== QUEUE STATUS ===\n');
  
  console.log('Main Queue:');
  console.log(`  Messages Available: ${mainAttrs.Attributes.ApproximateNumberOfMessages}`);
  console.log(`  Messages In Flight: ${mainAttrs.Attributes.ApproximateNumberOfMessagesNotVisible}`);
  console.log(`  Messages Delayed: ${mainAttrs.Attributes.ApproximateNumberOfMessagesDelayed}`);
  
  console.log('\nDead Letter Queue:');
  console.log(`  Messages Available: ${dlqAttrs.Attributes.ApproximateNumberOfMessages}`);
  console.log(`  Messages In Flight: ${dlqAttrs.Attributes.ApproximateNumberOfMessagesNotVisible}`);
  console.log(`  Messages Delayed: ${dlqAttrs.Attributes.ApproximateNumberOfMessagesDelayed}`);
}

checkQueues().catch(console.error);