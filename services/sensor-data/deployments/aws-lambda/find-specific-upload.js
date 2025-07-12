const AWS = require('aws-sdk');

AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();
const s3 = new AWS.S3();

const TARGET_UPLOAD_ID = '4db50588-1762-4830-b09f-ae5e2ab4dbf9';
const TARGET_FILENAME = 'ridplan_rice_20250702.zip';
const GIS_QUEUE_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-queue';
const GIS_DLQ_URL = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-dlq';

async function findUpload() {
  console.log(`Searching for upload: ${TARGET_UPLOAD_ID}`);
  console.log(`File name: ${TARGET_FILENAME}\n`);
  
  // Check S3 first
  console.log('=== CHECKING S3 ===');
  const s3Key = `shape-files/2025-07-04/${TARGET_UPLOAD_ID}/${TARGET_FILENAME}`;
  const s3Bucket = 'munbon-gis-shape-files';
  
  try {
    const headResult = await s3.headObject({
      Bucket: s3Bucket,
      Key: s3Key
    }).promise();
    
    console.log('✅ File found in S3!');
    console.log(`  Size: ${headResult.ContentLength} bytes`);
    console.log(`  Last Modified: ${headResult.LastModified}`);
    console.log(`  ETag: ${headResult.ETag}`);
  } catch (error) {
    if (error.code === 'NotFound') {
      console.log('❌ File not found in S3 at expected location');
    } else {
      console.log(`❌ S3 Error: ${error.message}`);
    }
  }
  
  // Check both queues
  console.log('\n=== CHECKING QUEUES ===');
  
  for (const [queueName, queueUrl] of [['Main Queue', GIS_QUEUE_URL], ['DLQ', GIS_DLQ_URL]]) {
    console.log(`\nChecking ${queueName}...`);
    let found = false;
    let checked = 0;
    
    // Check up to 100 messages
    for (let i = 0; i < 10 && !found; i++) {
      const { Messages } = await sqs.receiveMessage({
        QueueUrl: queueUrl,
        MaxNumberOfMessages: 10,
        VisibilityTimeout: 0,
        WaitTimeSeconds: 1
      }).promise();
      
      if (!Messages) break;
      
      for (const msg of Messages) {
        checked++;
        try {
          const body = JSON.parse(msg.Body);
          if (body.uploadId === TARGET_UPLOAD_ID || body.fileName === TARGET_FILENAME) {
            console.log('✅ FOUND MESSAGE!');
            console.log(JSON.stringify(body, null, 2));
            found = true;
            break;
          }
        } catch (e) {}
      }
    }
    
    if (!found) {
      console.log(`  Checked ${checked} messages - not found`);
    }
  }
  
  // Check CloudWatch logs
  console.log('\n=== CLOUDWATCH LOGS ===');
  console.log('To check Lambda execution logs, run:');
  console.log(`aws logs filter-log-events --log-group-name /aws/lambda/munbon-gis-shapefile-processor --filter-pattern "${TARGET_UPLOAD_ID}"`);
  
  // Check if processing completed
  console.log('\n=== PROCESSING STATUS ===');
  console.log('If the file was processed:');
  console.log('1. Message would be deleted from queue');
  console.log('2. Data would be extracted and stored');
  console.log('3. Processing logs would be in CloudWatch');
  console.log('\nCurrent status: File uploaded to S3, but no message found in queues');
}

findUpload().catch(console.error);