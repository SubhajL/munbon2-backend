import { APIGatewayProxyHandler, SQSHandler } from 'aws-lambda';
import AWS from 'aws-sdk';
import { v4 as uuidv4 } from 'uuid';
import { ShapeFileController } from '../controllers/shapefile.controller';
import { ShapeFileService } from '../services/shapefile.service';
import { ParcelRepository } from '../repository/parcel.repository';
import { createLogger } from '../utils/logger';
import { config } from '../config';

const s3 = new AWS.S3();
const sqs = new AWS.SQS();
const logger = createLogger('Lambda');

// Initialize services (Note: In Lambda, we'll use environment variables for DB config)
const parcelRepo = new ParcelRepository(config.database);
const shapeFileService = new ShapeFileService(parcelRepo);
const controller = new ShapeFileController();

// Helper to parse multipart form data
const parseMultipartData = (event: any): { file: Buffer; filename: string; fields: any } => {
  // This is a simplified version - in production, use a proper multipart parser
  const boundary = event.headers['content-type'].split('boundary=')[1];
  const body = Buffer.from(event.body, event.isBase64Encoded ? 'base64' : 'utf8');
  
  // Parse multipart data (simplified - use busboy or similar in production)
  const parts = body.toString().split(`--${boundary}`);
  let file: Buffer | null = null;
  let filename = '';
  const fields: any = {};
  
  for (const part of parts) {
    if (part.includes('Content-Disposition: form-data')) {
      if (part.includes('filename=')) {
        const filenameMatch = part.match(/filename="([^"]+)"/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
        const dataStart = part.indexOf('\r\n\r\n') + 4;
        const dataEnd = part.lastIndexOf('\r\n');
        file = Buffer.from(part.slice(dataStart, dataEnd));
      } else {
        const nameMatch = part.match(/name="([^"]+)"/);
        if (nameMatch) {
          const fieldName = nameMatch[1];
          const dataStart = part.indexOf('\r\n\r\n') + 4;
          const dataEnd = part.lastIndexOf('\r\n');
          fields[fieldName] = part.slice(dataStart, dataEnd).trim();
        }
      }
    }
  }
  
  if (!file) {
    throw new Error('No file found in multipart data');
  }
  
  return { file, filename, fields };
};

export const shapeFileUpload: APIGatewayProxyHandler = async (event, context) => {
  try {
    const { file, filename, fields } = parseMultipartData(event);
    
    // Generate unique ID for this upload
    const uploadId = uuidv4();
    const s3Key = `uploads/${uploadId}/${filename}`;
    
    // Upload to S3
    await s3.putObject({
      Bucket: process.env.S3_BUCKET_NAME!,
      Key: s3Key,
      Body: file,
      Metadata: {
        originalName: filename,
        uploadId,
        description: fields.description || '',
        waterDemandMethod: fields.waterDemandMethod || 'RID-MS',
        processingInterval: fields.processingInterval || 'daily'
      }
    }).promise();
    
    // Send message to SQS for processing
    await sqs.sendMessage({
      QueueUrl: process.env.SQS_QUEUE_URL!,
      MessageBody: JSON.stringify({
        uploadId,
        s3Key,
        filename,
        metadata: fields,
        timestamp: new Date().toISOString()
      })
    }).promise();
    
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify({
        id: uploadId,
        filename,
        status: 'processing',
        message: 'Shape file uploaded successfully and queued for processing'
      })
    };
  } catch (error) {
    logger.error('Error uploading shape file:', error);
    return {
      statusCode: 500,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
      },
      body: JSON.stringify({
        error: 'Failed to upload shape file',
        message: error instanceof Error ? error.message : 'Unknown error'
      })
    };
  }
};

export const shapeFileMetadata: APIGatewayProxyHandler = async (event, context) => {
  try {
    const { id } = event.pathParameters || {};
    if (!id) {
      return {
        statusCode: 400,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify({ error: 'Shape file ID is required' })
      };
    }
    
    const metadata = await shapeFileService.getShapeFileMetadata(id);
    
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify(metadata)
    };
  } catch (error) {
    logger.error('Error getting shape file metadata:', error);
    return {
      statusCode: 404,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify({ error: 'Shape file not found' })
    };
  }
};

export const shapeFileList: APIGatewayProxyHandler = async (event, context) => {
  try {
    const queryParams = event.queryStringParameters || {};
    const options = {
      status: queryParams.status,
      page: parseInt(queryParams.page || '1'),
      limit: parseInt(queryParams.limit || '10'),
      sortBy: queryParams.sortBy || 'uploadDate',
      sortOrder: queryParams.sortOrder as 'asc' | 'desc' || 'desc'
    };
    
    const result = await shapeFileService.listShapeFiles(options);
    
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify(result)
    };
  } catch (error) {
    logger.error('Error listing shape files:', error);
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify({ error: 'Failed to list shape files' })
    };
  }
};

export const shapeFileParcels: APIGatewayProxyHandler = async (event, context) => {
  try {
    const { id } = event.pathParameters || {};
    if (!id) {
      return {
        statusCode: 400,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify({ error: 'Shape file ID is required' })
      };
    }
    
    const queryParams = event.queryStringParameters || {};
    const filters = {
      zone: queryParams.zone,
      cropType: queryParams.cropType,
      waterDemandMethod: queryParams.waterDemandMethod as any
    };
    
    const pagination = {
      page: parseInt(queryParams.page || '1'),
      limit: parseInt(queryParams.limit || '100')
    };
    
    const result = await shapeFileService.getParcels(id, filters, pagination);
    
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify(result)
    };
  } catch (error) {
    logger.error('Error getting parcels:', error);
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify({ error: 'Failed to get parcels' })
    };
  }
};

export const shapeFileExport: APIGatewayProxyHandler = async (event, context) => {
  try {
    const { id } = event.pathParameters || {};
    if (!id) {
      return {
        statusCode: 400,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify({ error: 'Shape file ID is required' })
      };
    }
    
    const includeWaterDemand = event.queryStringParameters?.includeWaterDemand === 'true';
    const geojson = await shapeFileService.exportAsGeoJSON(id, includeWaterDemand);
    
    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Content-Disposition': `attachment; filename="shapefile-${id}.geojson"`
      },
      body: JSON.stringify(geojson)
    };
  } catch (error) {
    logger.error('Error exporting shape file:', error);
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify({ error: 'Failed to export shape file' })
    };
  }
};

// SQS Handler for processing shape files
export const processShapeFile: SQSHandler = async (event, context) => {
  for (const record of event.Records) {
    try {
      const message = JSON.parse(record.body);
      const { uploadId, s3Key, filename, metadata } = message;
      
      logger.info(`Processing shape file: ${uploadId}`);
      
      // Download file from S3
      const s3Object = await s3.getObject({
        Bucket: process.env.S3_BUCKET_NAME!,
        Key: s3Key
      }).promise();
      
      const fileBuffer = s3Object.Body as Buffer;
      
      // Process the shape file
      await shapeFileService.processShapeFile({
        id: uploadId,
        filename,
        buffer: fileBuffer,
        metadata
      });
      
      // Move file to processed folder
      await s3.copyObject({
        Bucket: process.env.S3_BUCKET_NAME!,
        CopySource: `${process.env.S3_BUCKET_NAME}/${s3Key}`,
        Key: s3Key.replace('uploads/', 'processed/')
      }).promise();
      
      // Delete original
      await s3.deleteObject({
        Bucket: process.env.S3_BUCKET_NAME!,
        Key: s3Key
      }).promise();
      
      logger.info(`Successfully processed shape file: ${uploadId}`);
    } catch (error) {
      logger.error('Error processing shape file:', error);
      throw error; // This will send the message to DLQ after retries
    }
  }
};