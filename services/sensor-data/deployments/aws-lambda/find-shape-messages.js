const AWS = require('aws-sdk');

// Configure AWS
AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();

const QUEUE_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';

async function findShapeFileMessages() {
  let foundShapeFiles = [];
  let attempts = 0;
  const maxAttempts = 10;

  console.log('Searching for SHAPE file messages in SQS...\n');

  while (attempts < maxAttempts && foundShapeFiles.length === 0) {
    attempts++;
    console.log(`Attempt ${attempts}/${maxAttempts}...`);

    try {
      // Receive messages (without deleting)
      const messages = await sqs.receiveMessage({
        QueueUrl: QUEUE_URL,
        MaxNumberOfMessages: 10,
        VisibilityTimeout: 0, // Don't hide messages
        WaitTimeSeconds: 2
      }).promise();

      if (messages.Messages) {
        messages.Messages.forEach(msg => {
          try {
            const body = JSON.parse(msg.Body);
            if (body.type === 'shape-file') {
              foundShapeFiles.push({
                messageId: msg.MessageId,
                receiptHandle: msg.ReceiptHandle,
                body: body
              });
            }
          } catch (e) {
            // Skip non-JSON messages
          }
        });
      }
    } catch (error) {
      console.error('Error receiving messages:', error.message);
      break;
    }
  }

  if (foundShapeFiles.length === 0) {
    console.log('\nNo SHAPE file messages found in the first ' + (attempts * 10) + ' messages checked.');
    console.log('The SHAPE file message might be further down in the queue.');
    console.log('\nNote: Your recent upload with ID 32d19024-76ec-44b1-b8e0-7ca560b081a3 should be in the queue.');
  } else {
    console.log(`\nFound ${foundShapeFiles.length} SHAPE file message(s):\n`);
    
    foundShapeFiles.forEach((shapeMsg, index) => {
      const body = shapeMsg.body;
      console.log(`SHAPE File Upload ${index + 1}:`);
      console.log(`- Message ID: ${shapeMsg.messageId}`);
      console.log(`- Upload ID: ${body.uploadId}`);
      console.log(`- File Name: ${body.fileName}`);
      console.log(`- S3 Location: s3://${body.s3Bucket}/${body.s3Key}`);
      console.log(`- Water Demand Method: ${body.waterDemandMethod}`);
      console.log(`- Processing Interval: ${body.processingInterval}`);
      console.log(`- Uploaded At: ${body.uploadedAt}`);
      if (body.metadata?.zone) {
        console.log(`- Zone: ${body.metadata.zone}`);
      }
      if (body.metadata?.description) {
        console.log(`- Description: ${body.metadata.description}`);
      }
      console.log('---\n');
    });
  }

  // Also check the most recent messages by looking at message attributes
  console.log('\nChecking for messages with dataType=shape-file attribute...');
  try {
    const attrMessages = await sqs.receiveMessage({
      QueueUrl: QUEUE_URL,
      MaxNumberOfMessages: 10,
      MessageAttributeNames: ['All'],
      VisibilityTimeout: 0,
      WaitTimeSeconds: 2
    }).promise();

    if (attrMessages.Messages) {
      const shapeAttrMessages = attrMessages.Messages.filter(msg => 
        msg.MessageAttributes?.dataType?.StringValue === 'shape-file'
      );

      if (shapeAttrMessages.length > 0) {
        console.log(`Found ${shapeAttrMessages.length} message(s) with shape-file attribute!`);
        // Process these messages...
      }
    }
  } catch (e) {
    console.error('Error checking message attributes:', e.message);
  }
}

// Run the search
findShapeFileMessages();