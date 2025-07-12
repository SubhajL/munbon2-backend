const AWS = require('aws-sdk');

// Configure AWS
AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();

const QUEUE_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';

async function processShapeMessages() {
  console.log('Processing queue to find and handle SHAPE file messages...\n');

  let processedCount = 0;
  let shapeFileCount = 0;
  let otherMessageCount = 0;

  try {
    while (processedCount < 100) { // Process up to 100 messages
      const messages = await sqs.receiveMessage({
        QueueUrl: QUEUE_URL,
        MaxNumberOfMessages: 10,
        VisibilityTimeout: 30, // Hide messages for 30 seconds while processing
        WaitTimeSeconds: 2,
        MessageAttributeNames: ['All']
      }).promise();

      if (!messages.Messages || messages.Messages.length === 0) {
        console.log('No more messages to process');
        break;
      }

      for (const message of messages.Messages) {
        processedCount++;
        
        try {
          const body = JSON.parse(message.Body);
          
          if (body.type === 'shape-file') {
            shapeFileCount++;
            console.log(`\n✅ Found SHAPE file message #${shapeFileCount}:`);
            console.log(`   Upload ID: ${body.uploadId}`);
            console.log(`   File: ${body.fileName}`);
            console.log(`   S3: s3://${body.s3Bucket}/${body.s3Key}`);
            console.log(`   Uploaded: ${body.uploadedAt}`);
            
            // Option to delete the message after processing
            // await sqs.deleteMessage({
            //   QueueUrl: QUEUE_URL,
            //   ReceiptHandle: message.ReceiptHandle
            // }).promise();
            // console.log('   Message deleted from queue');
          } else {
            otherMessageCount++;
            // For non-shape messages, we could delete them or let them expire
          }
        } catch (e) {
          console.error(`Error processing message: ${e.message}`);
        }
      }

      process.stdout.write(`\rProcessed ${processedCount} messages (${shapeFileCount} SHAPE files, ${otherMessageCount} other)`);
    }

    console.log(`\n\nSummary:`);
    console.log(`- Total messages processed: ${processedCount}`);
    console.log(`- SHAPE file messages found: ${shapeFileCount}`);
    console.log(`- Other messages: ${otherMessageCount}`);

  } catch (error) {
    console.error('\nError:', error.message);
  }
}

// Add option to delete old sensor messages
async function cleanOldSensorMessages() {
  console.log('\nCleaning old sensor messages (keeping SHAPE file messages)...\n');
  
  let deletedCount = 0;
  const cutoffDate = new Date('2025-06-20'); // Delete messages older than this

  while (deletedCount < 1000) { // Clean up to 1000 old messages
    const messages = await sqs.receiveMessage({
      QueueUrl: QUEUE_URL,
      MaxNumberOfMessages: 10,
      VisibilityTimeout: 10
    }).promise();

    if (!messages.Messages || messages.Messages.length === 0) break;

    const deletePromises = [];
    
    for (const message of messages.Messages) {
      try {
        const body = JSON.parse(message.Body);
        
        // Only delete old sensor messages, keep SHAPE files
        if (body.type !== 'shape-file' && new Date(body.timestamp) < cutoffDate) {
          deletePromises.push(
            sqs.deleteMessage({
              QueueUrl: QUEUE_URL,
              ReceiptHandle: message.ReceiptHandle
            }).promise()
          );
          deletedCount++;
        }
      } catch (e) {
        // Skip non-JSON messages
      }
    }

    await Promise.all(deletePromises);
    process.stdout.write(`\rDeleted ${deletedCount} old sensor messages`);
  }

  console.log(`\n\nCleanup complete. Deleted ${deletedCount} old messages.`);
}

// Menu
console.log('SQS Queue Management for SHAPE Files');
console.log('===================================\n');
console.log('1. Process queue to find SHAPE file messages');
console.log('2. Clean old sensor messages (keep SHAPE files)');
console.log('\nPress Ctrl+C to exit\n');

// Run the processor
processShapeMessages();