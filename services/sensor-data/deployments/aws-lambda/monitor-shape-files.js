const AWS = require('aws-sdk');

AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();

async function monitorShapeFiles() {
  const queueUrl = process.env.QUEUE_URL || 
    'https://sqs.ap-southeast-1.amazonaws.com/YOUR_ACCOUNT_ID/munbon-sensor-ingestion-dev-queue';

  console.log('Monitoring for shape file messages...\n');

  setInterval(async () => {
    try {
      const { Messages } = await sqs.receiveMessage({
        QueueUrl: queueUrl,
        MaxNumberOfMessages: 10,
        VisibilityTimeout: 0,
        MessageAttributeNames: ['All'],
        WaitTimeSeconds: 5
      }).promise();

      if (Messages) {
        const shapeMessages = Messages.filter(msg => {
          try {
            const body = JSON.parse(msg.Body);
            return body.type === 'shape-file';
          } catch {
            return false;
          }
        });

        if (shapeMessages.length > 0) {
          console.log(`[${new Date().toISOString()}] Found ${shapeMessages.length} shape file messages:`);
          shapeMessages.forEach(msg => {
            const body = JSON.parse(msg.Body);
            console.log(`  - ${body.fileName} (${body.uploadId})`);
          });
        }
      }
    } catch (error) {
      console.error('Monitor error:', error.message);
    }
  }, 10000); // Check every 10 seconds
}

// First list queues to find the right one
sqs.listQueues({ QueueNamePrefix: 'munbon-sensor-ingestion' }).promise()
  .then(({ QueueUrls }) => {
    if (QueueUrls && QueueUrls.length > 0) {
      console.log('Using queue:', QueueUrls[0]);
      process.env.QUEUE_URL = QueueUrls[0];
      monitorShapeFiles();
    }
  })
  .catch(console.error);