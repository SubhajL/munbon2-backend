import 'dotenv/config';
import * as AWS from 'aws-sdk';
import { AppDataSource } from './src/config/database';
import { ShapeFileUpload, UploadStatus } from './src/models/shape-file-upload.entity';
import { ParcelSimple } from './src/models/parcel-simple.entity';

AWS.config.update({ region: 'ap-southeast-1' });
const sqs = new AWS.SQS();
const s3 = new AWS.S3();

async function processMessage() {
  try {
    // Initialize database
    console.log('Initializing database...');
    await AppDataSource.initialize();
    console.log('Database initialized');
    
    // Get message from queue
    const queueUrl = process.env.GIS_SQS_QUEUE_URL!;
    console.log('Receiving from queue:', queueUrl);
    
    const { Messages } = await sqs.receiveMessage({
      QueueUrl: queueUrl,
      MaxNumberOfMessages: 1,
    }).promise();
    
    if (!Messages || Messages.length === 0) {
      console.log('No messages in queue');
      return;
    }
    
    const message = Messages[0];
    const messageData = JSON.parse(message.Body!);
    console.log('Processing message:', messageData.uploadId);
    
    // Create upload record
    const uploadRepo = AppDataSource.getRepository(ShapeFileUpload);
    const upload = new ShapeFileUpload();
    upload.uploadId = messageData.uploadId;
    upload.fileName = messageData.fileName;
    upload.s3Key = messageData.s3Key;
    upload.status = UploadStatus.PROCESSING;
    await uploadRepo.save(upload);
    console.log('Upload record created');
    
    // Download from S3
    const s3Object = await s3.getObject({
      Bucket: messageData.s3Bucket,
      Key: messageData.s3Key,
    }).promise();
    console.log('Downloaded from S3, size:', (s3Object.Body as Buffer)?.length);
    
    // For now, just create dummy parcels
    const parcelRepo = AppDataSource.getRepository(ParcelSimple);
    for (let i = 0; i < 3; i++) {
      const parcel = new ParcelSimple();
      parcel.uploadId = messageData.uploadId;
      parcel.parcelCode = `P-${messageData.uploadId}-${i}`;
      parcel.zoneId = '1';
      parcel.area = 1000 + i * 500;
      parcel.geometry = { type: 'Polygon', coordinates: [[]] };
      await parcelRepo.save(parcel);
    }
    console.log('Created 3 test parcels');
    
    // Update upload status
    upload.status = UploadStatus.COMPLETED;
    upload.parcelCount = 3;
    upload.completedAt = new Date();
    await uploadRepo.save(upload);
    console.log('Upload marked as completed');
    
    // Delete message from queue
    if (message.ReceiptHandle) {
      await sqs.deleteMessage({
        QueueUrl: queueUrl,
        ReceiptHandle: message.ReceiptHandle,
      }).promise();
      console.log('Message deleted from queue');
    }
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await AppDataSource.destroy();
  }
}

processMessage();