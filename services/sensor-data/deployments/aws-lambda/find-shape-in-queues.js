const AWS = require('aws-sdk');

AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();

async function findShapeFiles() {
  const mainQueueUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-queue';
  const dlqUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-sensor-ingestion-dev-dlq';
  
  console.log('=== SEARCHING FOR SHAPE FILES ===\n');
  
  // Check main queue
  console.log('Checking main queue...');
  let foundInMain = 0;
  for (let i = 0; i < 10; i++) {
    const { Messages } = await sqs.receiveMessage({
      QueueUrl: mainQueueUrl,
      MaxNumberOfMessages: 10,
      VisibilityTimeout: 0,
      WaitTimeSeconds: 1
    }).promise();
    
    if (Messages) {
      for (const msg of Messages) {
        try {
          const body = JSON.parse(msg.Body);
          if (body.type === 'shape-file' || body.fileName?.endsWith('.zip')) {
            foundInMain++;
            console.log('Found shape file in main queue:', {
              fileName: body.fileName,
              uploadId: body.uploadId,
              uploadedAt: body.uploadedAt
            });
          }
        } catch (e) {}
      }
    }
  }
  
  // Check DLQ
  console.log('\nChecking DLQ...');
  let foundInDLQ = 0;
  for (let i = 0; i < 10; i++) {
    const { Messages } = await sqs.receiveMessage({
      QueueUrl: dlqUrl,
      MaxNumberOfMessages: 10,
      VisibilityTimeout: 0,
      WaitTimeSeconds: 1
    }).promise();
    
    if (Messages) {
      for (const msg of Messages) {
        try {
          const body = JSON.parse(msg.Body);
          if (body.type === 'shape-file' || body.fileName?.endsWith('.zip')) {
            foundInDLQ++;
            console.log('Found shape file in DLQ:', {
              fileName: body.fileName,
              uploadId: body.uploadId,
              uploadedAt: body.uploadedAt,
              type: body.type
            });
          }
        } catch (e) {}
      }
    }
  }
  
  console.log(`\nSummary: Found ${foundInMain} shape files in main queue, ${foundInDLQ} in DLQ`);
  
  // Check S3
  const s3 = new AWS.S3();
  const bucketName = 'munbon-shape-files-dev';
  
  try {
    const { Contents } = await s3.listObjectsV2({
      Bucket: bucketName,
      Prefix: 'shape-files/',
      MaxKeys: 10
    }).promise();
    
    console.log(`\nShape files in S3 bucket '${bucketName}':`);
    if (Contents && Contents.length > 0) {
      Contents.forEach(obj => {
        console.log(`  - ${obj.Key} (${obj.Size} bytes, ${obj.LastModified})`);
      });
    } else {
      console.log('  No files found');
    }
  } catch (error) {
    console.log('\nError checking S3:', error.message);
  }
}

findShapeFiles().catch(console.error);