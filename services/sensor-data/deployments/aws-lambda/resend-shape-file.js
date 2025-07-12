const AWS = require('aws-sdk');

AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();

async function resendShapeFile() {
  const mainQueueUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';
  
  // The shape file we uploaded
  const shapeFileMessage = {
    type: 'shape-file',
    sensorType: 'shape-file',
    uploadId: '776d50c0-b4b2-49f5-b657-63c797a08047',
    s3Bucket: 'munbon-shape-files-dev',
    s3Key: 'shape-files/2025-06-30/776d50c0-b4b2-49f5-b657-63c797a08047/data_rice_20250616_merge.zip',
    fileName: 'data_rice_20250616_merge.zip',
    waterDemandMethod: 'RID-MS',
    processingInterval: 'weekly',
    uploadedAt: '2025-06-30T13:59:00.000Z',
    source: 'manual-resend',
    metadata: {
      description: 'Rice cultivation data for June 2025',
      zone: 'Zone 1'
    }
  };

  console.log('Sending shape file message to queue...');
  console.log(JSON.stringify(shapeFileMessage, null, 2));
  
  try {
    const result = await sqs.sendMessage({
      QueueUrl: mainQueueUrl,
      MessageBody: JSON.stringify(shapeFileMessage),
      MessageAttributes: {
        uploadId: {
          DataType: 'String',
          StringValue: shapeFileMessage.uploadId
        },
        dataType: {
          DataType: 'String',
          StringValue: 'shape-file'
        }
      }
    }).promise();
    
    console.log('\nMessage sent successfully!');
    console.log('Message ID:', result.MessageId);
    console.log('\nThe consumer should process this message and save it to the database.');
  } catch (error) {
    console.error('Error sending message:', error);
  }
}

resendShapeFile().catch(console.error);