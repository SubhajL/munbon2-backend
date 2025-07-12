const AWS = require('aws-sdk');

// Configure AWS
AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();

const QUEUE_NAME = 'munbon-sensor-ingestion-dev-queue';

async function checkSQSMessages() {
  try {
    // Get queue URL
    const queueUrlResult = await sqs.getQueueUrl({ QueueName: QUEUE_NAME }).promise();
    const queueUrl = queueUrlResult.QueueUrl;
    console.log(`Queue URL: ${queueUrl}\n`);

    // Get queue attributes
    const attributes = await sqs.getQueueAttributes({
      QueueUrl: queueUrl,
      AttributeNames: ['All']
    }).promise();

    console.log('Queue Statistics:');
    console.log(`- Messages Available: ${attributes.Attributes.ApproximateNumberOfMessages}`);
    console.log(`- Messages In Flight: ${attributes.Attributes.ApproximateNumberOfMessagesNotVisible}`);
    console.log(`- Messages Delayed: ${attributes.Attributes.ApproximateNumberOfMessagesDelayed}\n`);

    // Receive messages (without deleting)
    const messages = await sqs.receiveMessage({
      QueueUrl: queueUrl,
      MaxNumberOfMessages: 10,
      VisibilityTimeout: 0, // Don't hide messages from other consumers
      WaitTimeSeconds: 5
    }).promise();

    if (!messages.Messages || messages.Messages.length === 0) {
      console.log('No messages in queue');
      return;
    }

    console.log(`Found ${messages.Messages.length} message(s):\n`);

    messages.Messages.forEach((msg, index) => {
      console.log(`Message ${index + 1}:`);
      console.log(`- Message ID: ${msg.MessageId}`);
      
      try {
        const body = JSON.parse(msg.Body);
        if (body.type === 'shape-file') {
          console.log('- Type: SHAPE File Upload');
          console.log(`- Upload ID: ${body.uploadId}`);
          console.log(`- File Name: ${body.fileName}`);
          console.log(`- S3 Location: s3://${body.s3Bucket}/${body.s3Key}`);
          console.log(`- Water Demand Method: ${body.waterDemandMethod}`);
          console.log(`- Processing Interval: ${body.processingInterval}`);
          console.log(`- Uploaded At: ${body.uploadedAt}`);
          if (body.metadata.zone) {
            console.log(`- Zone: ${body.metadata.zone}`);
          }
          if (body.metadata.description) {
            console.log(`- Description: ${body.metadata.description}`);
          }
        } else {
          console.log(`- Type: ${body.type}`);
          console.log(`- Body: ${JSON.stringify(body, null, 2)}`);
        }
      } catch (e) {
        console.log(`- Raw Body: ${msg.Body}`);
      }
      
      console.log(`- Receipt Handle: ${msg.ReceiptHandle.substring(0, 50)}...`);
      console.log('---');
    });

    console.log('\nTo process and delete a message, use the receipt handle with:');
    console.log('await sqs.deleteMessage({ QueueUrl: queueUrl, ReceiptHandle: receiptHandle }).promise()');

  } catch (error) {
    console.error('Error:', error.message);
    if (error.code === 'AWS.SimpleQueueService.NonExistentQueue') {
      console.error('Queue does not exist. Make sure the Lambda has been deployed.');
    } else if (error.code === 'CredentialsError') {
      console.error('AWS credentials not configured. Run: aws configure');
    }
  }
}

// Run the check
checkSQSMessages();