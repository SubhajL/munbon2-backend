const AWS = require('aws-sdk');

// Configure AWS
AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();

async function checkQueue() {
  try {
    // List queues to find the correct URL
    const { QueueUrls } = await sqs.listQueues({
      QueueNamePrefix: 'munbon-sensor-ingestion'
    }).promise();

    if (!QueueUrls || QueueUrls.length === 0) {
      console.log('No queues found with prefix: munbon-sensor-ingestion');
      return;
    }

    console.log('Found queues:', QueueUrls);

    // Check each queue
    for (const queueUrl of QueueUrls) {
      console.log(`\n=== Checking Queue: ${queueUrl} ===`);
      
      // Get queue attributes
      const { Attributes } = await sqs.getQueueAttributes({
        QueueUrl: queueUrl,
        AttributeNames: ['All']
      }).promise();

      console.log('Messages Available:', Attributes.ApproximateNumberOfMessages);
      console.log('Messages In Flight:', Attributes.ApproximateNumberOfMessagesNotVisible);
      console.log('Messages Delayed:', Attributes.ApproximateNumberOfMessagesDelayed);
      
      // Peek at messages without deleting
      const { Messages } = await sqs.receiveMessage({
        QueueUrl: queueUrl,
        MaxNumberOfMessages: 5,
        VisibilityTimeout: 0, // Don't hide messages
        WaitTimeSeconds: 1
      }).promise();

      if (Messages && Messages.length > 0) {
        console.log(`\nSample Messages (${Messages.length}):`);
        Messages.forEach((msg, idx) => {
          try {
            const body = JSON.parse(msg.Body);
            console.log(`\nMessage ${idx + 1}:`);
            console.log('- Type:', body.type || 'Unknown');
            console.log('- Upload ID:', body.uploadId || 'N/A');
            console.log('- File:', body.fileName || 'N/A');
            console.log('- Timestamp:', body.uploadedAt || body.timestamp || 'N/A');
            console.log('- Message ID:', msg.MessageId);
          } catch (e) {
            console.log(`Message ${idx + 1}: Unable to parse - ${msg.Body.substring(0, 100)}...`);
          }
        });
      } else {
        console.log('\nNo messages in queue');
      }
    }
  } catch (error) {
    console.error('Error:', error.message);
    console.log('\nMake sure you have AWS credentials configured:');
    console.log('- aws configure');
    console.log('- or export AWS_PROFILE=your-profile');
  }
}

checkQueue();