const AWS = require('aws-sdk');

// Configure AWS
AWS.config.update({ region: 'ap-southeast-1' });
const s3 = new AWS.S3();

const bucketName = 'munbon-gis-shape-files';

async function createBucket() {
  try {
    // Check if bucket exists
    try {
      await s3.headBucket({ Bucket: bucketName }).promise();
      console.log(`✅ Bucket ${bucketName} already exists`);
      return;
    } catch (err) {
      if (err.code !== 'NotFound') {
        throw err;
      }
      console.log(`Bucket ${bucketName} not found, creating...`);
    }

    // Create bucket
    const params = {
      Bucket: bucketName,
      CreateBucketConfiguration: {
        LocationConstraint: 'ap-southeast-1'
      }
    };

    await s3.createBucket(params).promise();
    console.log(`✅ Bucket ${bucketName} created successfully`);

    // Enable versioning
    await s3.putBucketVersioning({
      Bucket: bucketName,
      VersioningConfiguration: {
        Status: 'Enabled'
      }
    }).promise();
    console.log('✅ Versioning enabled');

    // Set CORS configuration
    const corsParams = {
      Bucket: bucketName,
      CORSConfiguration: {
        CORSRules: [{
          AllowedHeaders: ['*'],
          AllowedMethods: ['PUT', 'POST', 'GET', 'HEAD'],
          AllowedOrigins: ['*'],
          MaxAgeSeconds: 3000
        }]
      }
    };
    
    await s3.putBucketCors(corsParams).promise();
    console.log('✅ CORS configuration set');

  } catch (error) {
    console.error('Error:', error.message);
    if (error.code === 'BucketAlreadyOwnedByYou') {
      console.log('✅ Bucket already exists and is owned by you');
    } else {
      throw error;
    }
  }
}

createBucket().catch(console.error);