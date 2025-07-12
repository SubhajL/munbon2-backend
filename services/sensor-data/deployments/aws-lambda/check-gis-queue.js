const AWS = require('aws-sdk');

AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();

const GIS_QUEUE_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-queue';
const GIS_DLQ_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-dlq';

async function checkGISQueues() {
  console.log('=== GIS SHAPEFILE QUEUE STATUS ===\n');
  
  // Check main queue
  const mainAttrs = await sqs.getQueueAttributes({
    QueueUrl: GIS_QUEUE_URL,
    AttributeNames: ['All']
  }).promise();
  
  console.log('Main GIS Queue:');
  console.log(`  Messages Available: ${mainAttrs.Attributes.ApproximateNumberOfMessages}`);
  console.log(`  Messages In Flight: ${mainAttrs.Attributes.ApproximateNumberOfMessagesNotVisible}`);
  console.log(`  Messages Delayed: ${mainAttrs.Attributes.ApproximateNumberOfMessagesDelayed}`);
  
  // Check DLQ
  const dlqAttrs = await sqs.getQueueAttributes({
    QueueUrl: GIS_DLQ_URL,
    AttributeNames: ['All']
  }).promise();
  
  console.log('\nGIS Dead Letter Queue:');
  console.log(`  Messages Available: ${dlqAttrs.Attributes.ApproximateNumberOfMessages}`);
  console.log(`  Messages In Flight: ${dlqAttrs.Attributes.ApproximateNumberOfMessagesNotVisible}`);
  console.log(`  Messages Delayed: ${dlqAttrs.Attributes.ApproximateNumberOfMessagesDelayed}`);
  
  // Look for recent messages
  console.log('\n=== SEARCHING FOR RECENT SHAPE FILE UPLOADS ===\n');
  
  const { Messages } = await sqs.receiveMessage({
    QueueUrl: GIS_QUEUE_URL,
    MaxNumberOfMessages: 10,
    VisibilityTimeout: 0,
    WaitTimeSeconds: 2,
    MessageAttributeNames: ['All']
  }).promise();
  
  if (Messages && Messages.length > 0) {
    console.log(`Found ${Messages.length} messages in queue:`);
    Messages.forEach((msg, idx) => {
      try {
        const body = JSON.parse(msg.Body);
        console.log(`\nMessage ${idx + 1}:`);
        console.log(`  Upload ID: ${body.uploadId}`);
        console.log(`  File: ${body.fileName}`);
        console.log(`  S3 Location: s3://${body.s3Bucket}/${body.s3Key}`);
        console.log(`  Uploaded: ${body.uploadedAt}`);
        
        if (body.uploadId === '4db50588-1762-4830-b09f-ae5e2ab4dbf9') {
          console.log('  *** THIS IS YOUR RECENT UPLOAD! ***');
        }
      } catch (e) {
        console.log(`  Parse error: ${e.message}`);
      }
    });
  } else {
    console.log('No messages found in the main queue');
  }
}

checkGISQueues().catch(console.error);