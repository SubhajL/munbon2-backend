const AWS = require('aws-sdk');

AWS.config.update({ region: 'ap-southeast-1' });
const s3 = new AWS.S3();
const sqs = new AWS.SQS();

async function migrateShapeFile() {
  // The shape file we uploaded earlier
  const sourceKey = 'shape-files/2025-06-30/776d50c0-b4b2-49f5-b657-63c797a08047/data_rice_20250616_merge.zip';
  const sourceBucket = 'munbon-shape-files-dev';
  
  // New GIS bucket
  const destBucket = 'munbon-gis-shape-files';
  const destKey = sourceKey; // Keep same structure
  
  console.log('Migrating shape file from sensor-data to GIS...\n');
  
  try {
    // Copy the file
    console.log(`Copying from s3://${sourceBucket}/${sourceKey}`);
    console.log(`         to s3://${destBucket}/${destKey}`);
    
    await s3.copyObject({
      CopySource: `${sourceBucket}/${sourceKey}`,
      Bucket: destBucket,
      Key: destKey,
      MetadataDirective: 'COPY',
    }).promise();
    
    console.log('✅ File copied successfully');
    
    // Send message to GIS queue
    const queueUrl = process.env.GIS_SQS_QUEUE_URL || 
      'https://sqs.ap-southeast-1.amazonaws.com/108728974441/munbon-gis-shapefile-queue';
    
    const message = {
      type: 'shape-file',
      uploadId: '776d50c0-b4b2-49f5-b657-63c797a08047',
      s3Bucket: destBucket,
      s3Key: destKey,
      fileName: 'data_rice_20250616_merge.zip',
      waterDemandMethod: 'RID-MS',
      processingInterval: 'weekly',
      metadata: {
        description: 'Rice cultivation data for June 2025',
        zone: 'Zone1',
        migratedFrom: 'sensor-data',
      },
      uploadedAt: '2025-06-30T13:59:00.000Z',
    };
    
    const result = await sqs.sendMessage({
      QueueUrl: queueUrl,
      MessageBody: JSON.stringify(message),
      MessageAttributes: {
        uploadId: {
          DataType: 'String',
          StringValue: message.uploadId,
        },
        dataType: {
          DataType: 'String',
          StringValue: 'shape-file',
        },
      },
    }).promise();
    
    console.log('✅ Message sent to GIS queue');
    console.log('Message ID:', result.MessageId);
    console.log('\nThe GIS service can now process this shape file!');
    
  } catch (error) {
    console.error('Error:', error.message);
    if (error.code === 'NoSuchBucket') {
      console.log('\nPlease run setup-aws-resources.sh first to create the GIS bucket');
    }
  }
}

migrateShapeFile().catch(console.error);