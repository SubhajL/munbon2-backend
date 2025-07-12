const AWS = require('aws-sdk');

AWS.config.update({ region: 'ap-southeast-1' });
const s3 = new AWS.S3();
const sqs = new AWS.SQS();

async function checkUploadStatus() {
  console.log('=== GIS Shape File Upload Status ===\n');

  // 1. Check S3 for uploaded files
  console.log('1. Checking S3 bucket for shape files...');
  try {
    const listParams = {
      Bucket: 'munbon-gis-shape-files',
      Prefix: 'shape-files/'
    };
    
    const objects = await s3.listObjectsV2(listParams).promise();
    
    if (objects.Contents && objects.Contents.length > 0) {
      console.log(`✅ Found ${objects.Contents.length} files in S3:`);
      objects.Contents.forEach(obj => {
        console.log(`   - ${obj.Key} (${(obj.Size / 1024 / 1024).toFixed(2)} MB, uploaded: ${obj.LastModified})`);
      });
    } else {
      console.log('❌ No files found in S3');
    }
  } catch (error) {
    console.error('Error checking S3:', error.message);
  }

  console.log('\n2. Checking SQS queue for messages...');
  try {
    const queueUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-queue';
    
    const queueAttributes = await sqs.getQueueAttributes({
      QueueUrl: queueUrl,
      AttributeNames: ['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
    }).promise();
    
    console.log('Queue status:');
    console.log(`   - Messages available: ${queueAttributes.Attributes.ApproximateNumberOfMessages}`);
    console.log(`   - Messages in flight: ${queueAttributes.Attributes.ApproximateNumberOfMessagesNotVisible}`);
    
    // Peek at messages without deleting
    const messages = await sqs.receiveMessage({
      QueueUrl: queueUrl,
      MaxNumberOfMessages: 5,
      VisibilityTimeout: 0
    }).promise();
    
    if (messages.Messages) {
      console.log(`\n   Found ${messages.Messages.length} messages:`);
      messages.Messages.forEach((msg, i) => {
        const body = JSON.parse(msg.Body);
        console.log(`   Message ${i + 1}: ${body.fileName} (uploadId: ${body.uploadId})`);
      });
    }
  } catch (error) {
    console.error('Error checking SQS:', error.message);
  }

  console.log('\n3. Checking DLQ for failed messages...');
  try {
    const dlqUrl = 'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-dlq';
    
    const dlqAttributes = await sqs.getQueueAttributes({
      QueueUrl: dlqUrl,
      AttributeNames: ['ApproximateNumberOfMessages']
    }).promise();
    
    console.log(`   - DLQ messages: ${dlqAttributes.Attributes.ApproximateNumberOfMessages}`);
  } catch (error) {
    console.error('Error checking DLQ:', error.message);
  }

  console.log('\n4. Processing status:');
  console.log('   ⚠️  Note: To process the uploaded files, you need to:');
  console.log('      1. Start the GIS service: cd services/gis && npm run dev');
  console.log('      2. Start the queue processor: cd services/gis && npm run queue:processor');
  console.log('      3. Check the database for processed parcels');
}

checkUploadStatus().catch(console.error);