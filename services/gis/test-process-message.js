const AWS = require('aws-sdk');
AWS.config.update({ region: 'ap-southeast-1' });

const sqs = new AWS.SQS();
const s3 = new AWS.S3();

const queueUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-queue';

async function processMessage() {
  try {
    // Receive message
    const { Messages } = await sqs.receiveMessage({
      QueueUrl: queueUrl,
      MaxNumberOfMessages: 1,
    }).promise();

    if (!Messages || Messages.length === 0) {
      console.log('No messages in queue');
      return;
    }

    const message = Messages[0];
    const messageData = JSON.parse(message.Body);
    console.log('Message:', messageData);

    // Try to download from S3
    try {
      const s3Object = await s3.getObject({
        Bucket: messageData.s3Bucket,
        Key: messageData.s3Key,
      }).promise();

      console.log('S3 Object downloaded successfully');
      console.log('Size:', s3Object.Body.length);
      console.log('ContentType:', s3Object.ContentType);
    } catch (s3Error) {
      console.error('S3 Error:', s3Error.message);
    }

  } catch (error) {
    console.error('Error:', error);
  }
}

processMessage();