import * as AWS from 'aws-sdk';
import { GeoPackageProcessor } from './src/services/geopackage-processor';
import { AppDataSource } from './src/config/database';
import { logger } from './src/utils/logger';
import * as fs from 'fs';
import * as path from 'path';
import AdmZip from 'adm-zip';

const s3 = new AWS.S3({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS({ region: 'ap-southeast-1' });

async function findS3Key(s3Client: AWS.S3, bucket: string, uploadId: string, fileName: string): Promise<string> {
  const params = {
    Bucket: bucket,
    Prefix: 'shape-files/',
  };
  
  const objects = await s3Client.listObjectsV2(params).promise();
  
  if (objects.Contents) {
    for (const obj of objects.Contents) {
      if (obj.Key && obj.Key.includes(uploadId) && obj.Key.endsWith(fileName)) {
        return obj.Key;
      }
    }
  }
  
  throw new Error(`S3 key not found for uploadId: ${uploadId}, fileName: ${fileName}`);
}

async function processGeoPackageFromS3() {
  try {
    // Initialize database
    if (!AppDataSource.isInitialized) {
      await AppDataSource.initialize();
    }

    // The specific file we're processing
    const uploadId = '62c52d9b-be71-4434-b9dd-189dfdab5941';
    const bucketName = 'munbon-gis-shape-files';
    
    // The S3 key pattern is: shape-files/{timestamp}/{uploadId}/{fileName}
    // We need to find the exact key by listing objects
    const s3Key = await findS3Key(s3, bucketName, uploadId, 'ridplan_rice_20250702.zip');
    
    logger.info('Processing GeoPackage from S3', { uploadId, s3Key });

    // Download from S3
    const s3Object = await s3.getObject({
      Bucket: bucketName,
      Key: s3Key,
    }).promise();

    if (!s3Object.Body) {
      throw new Error('Empty file received from S3');
    }

    // Extract ZIP to temp directory
    const tempDir = `/tmp/gis-geopackage-${uploadId}`;
    fs.mkdirSync(tempDir, { recursive: true });
    
    const zipPath = path.join(tempDir, 'archive.zip');
    fs.writeFileSync(zipPath, s3Object.Body as Buffer);
    
    const zip = new AdmZip(zipPath);
    zip.extractAllTo(tempDir, true);
    
    // Find .gpkg file
    const files = fs.readdirSync(tempDir);
    const gpkgFile = files.find(f => f.toLowerCase().endsWith('.gpkg'));
    
    if (!gpkgFile) {
      throw new Error('No .gpkg file found in archive');
    }
    
    const gpkgPath = path.join(tempDir, gpkgFile);
    logger.info('Found GeoPackage file', { file: gpkgFile });
    
    // Process GeoPackage
    const processor = new GeoPackageProcessor();
    const results = await processor.processGeoPackageFile(gpkgPath, uploadId);
    
    // Save to database
    const saveResults = await processor.saveProcessingResults(results);
    
    logger.info('GeoPackage processing completed', {
      uploadId,
      totalParcels: saveResults.totalParcels,
      totalZones: saveResults.totalZones,
      errors: saveResults.errors
    });
    
    // Clean up
    fs.rmSync(tempDir, { recursive: true, force: true });
    
    // Delete message from queue (if needed)
    const queueUrl = 'https://sqs.ap-southeast-1.amazonaws.com/471112912438/munbon-shapefile-queue';
    const messages = await sqs.receiveMessage({
      QueueUrl: queueUrl,
      MaxNumberOfMessages: 10,
      WaitTimeSeconds: 5,
    }).promise();
    
    if (messages.Messages) {
      for (const message of messages.Messages) {
        if (message.Body && message.ReceiptHandle) {
          const body = JSON.parse(message.Body);
          if (body.uploadId === uploadId) {
            await sqs.deleteMessage({
              QueueUrl: queueUrl,
              ReceiptHandle: message.ReceiptHandle,
            }).promise();
            logger.info('Deleted message from queue', { uploadId });
          }
        }
      }
    }
    
    process.exit(0);
  } catch (error) {
    logger.error('Failed to process GeoPackage', { error });
    process.exit(1);
  }
}

processGeoPackageFromS3();