import { APIGatewayProxyHandler, APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';
import * as AWS from 'aws-sdk';
import * as crypto from 'crypto';
import * as multipart from 'parse-multipart-data';

const s3 = new AWS.S3();
const sqs = new AWS.SQS();

// Bearer token authorizer
export const bearerTokenAuth = async (event: any): Promise<any> => {
  const token = event.authorizationToken?.replace('Bearer ', '');
  const validToken = process.env.EXTERNAL_UPLOAD_TOKEN || 'munbon-gis-shapefile';
  
  const isAuthorized = token === validToken;
  
  return {
    principalId: 'user',
    policyDocument: {
      Version: '2012-10-17',
      Statement: [
        {
          Action: 'execute-api:Invoke',
          Effect: isAuthorized ? 'Allow' : 'Deny',
          Resource: event.methodArn,
        },
      ],
    },
  };
};

// Main shapefile upload handler
export const shapefileUpload: APIGatewayProxyHandler = async (
  event: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> => {
  try {
    if (!event.body) {
      return {
        statusCode: 400,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ error: 'No file uploaded' }),
      };
    }

    // Parse multipart form data
    const boundary = multipart.getBoundary(event.headers['content-type'] || event.headers['Content-Type'] || '');
    const parts = multipart.parse(Buffer.from(event.body, 'base64'), boundary);
    
    if (parts.length === 0) {
      return {
        statusCode: 400,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ error: 'No file found in upload' }),
      };
    }

    const filePart = parts[0];
    const uploadId = crypto.randomUUID();
    const timestamp = new Date().toISOString().split('T')[0];
    const fileName = filePart.filename || 'shapefile.zip';
    const s3Key = `shape-files/${timestamp}/${uploadId}/${fileName}`;
    
    // Upload to S3
    const s3Params = {
      Bucket: process.env.SHAPE_FILE_BUCKET || 'munbon-gis-shape-files',
      Key: s3Key,
      Body: filePart.data,
      ContentType: 'application/zip',
      Metadata: {
        uploadId,
        originalName: fileName,
        uploadedAt: new Date().toISOString(),
      },
    };

    await s3.putObject(s3Params).promise();

    // Get additional metadata from request
    const metadata = event.queryStringParameters || {};
    
    // Send message to SQS
    const message = {
      type: 'shape-file',
      uploadId,
      s3Bucket: s3Params.Bucket,
      s3Key,
      fileName,
      waterDemandMethod: metadata.waterDemandMethod || 'RID-MS',
      processingInterval: metadata.processingInterval || 'weekly',
      metadata: {
        zone: metadata.zone,
        description: metadata.description,
        uploadedAt: new Date().toISOString(),
      },
    };

    const sqsParams = {
      QueueUrl: process.env.QUEUE_URL!,
      MessageBody: JSON.stringify(message),
      MessageAttributes: {
        uploadId: {
          DataType: 'String',
          StringValue: uploadId,
        },
        dataType: {
          DataType: 'String',
          StringValue: 'shape-file',
        },
      },
    };

    await sqs.sendMessage(sqsParams).promise();

    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        success: true,
        uploadId,
        message: 'Shape file uploaded successfully',
        location: `s3://${s3Params.Bucket}/${s3Key}`,
      }),
    };

  } catch (error) {
    console.error('Error processing shapefile upload:', error);
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        error: 'Failed to process shapefile upload',
        details: error instanceof Error ? error.message : 'Unknown error',
      }),
    };
  }
};

// Internal upload handler (no auth required)
export const internalShapefileUpload: APIGatewayProxyHandler = async (
  event: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> => {
  // For internal uploads, we process directly without auth check
  try {
    if (!event.body) {
      return {
        statusCode: 400,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ error: 'No file uploaded' }),
      };
    }

    // Parse multipart form data
    const boundary = multipart.getBoundary(event.headers['content-type'] || event.headers['Content-Type'] || '');
    const parts = multipart.parse(Buffer.from(event.body, 'base64'), boundary);
    
    if (parts.length === 0) {
      return {
        statusCode: 400,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ error: 'No file found in upload' }),
      };
    }

    const filePart = parts[0];
    const uploadId = crypto.randomUUID();
    const timestamp = new Date().toISOString().split('T')[0];
    const fileName = filePart.filename || 'shapefile.zip';
    const s3Key = `shape-files/${timestamp}/${uploadId}/${fileName}`;
    
    // Upload to S3
    const s3Params = {
      Bucket: process.env.SHAPE_FILE_BUCKET || 'munbon-gis-shape-files',
      Key: s3Key,
      Body: filePart.data,
      ContentType: 'application/zip',
      Metadata: {
        uploadId,
        originalName: fileName,
        uploadedAt: new Date().toISOString(),
        source: 'internal-api',
      },
    };

    await s3.putObject(s3Params).promise();

    // Get additional metadata from request
    const metadata = event.queryStringParameters || {};
    
    // Send message to SQS
    const message = {
      type: 'shape-file',
      uploadId,
      s3Bucket: s3Params.Bucket,
      s3Key,
      fileName,
      waterDemandMethod: metadata.waterDemandMethod || 'RID-MS',
      processingInterval: metadata.processingInterval || 'weekly',
      metadata: {
        zone: metadata.zone,
        description: metadata.description,
        uploadedAt: new Date().toISOString(),
        source: 'internal-api',
      },
    };

    const sqsParams = {
      QueueUrl: process.env.QUEUE_URL!,
      MessageBody: JSON.stringify(message),
      MessageAttributes: {
        uploadId: {
          DataType: 'String',
          StringValue: uploadId,
        },
        dataType: {
          DataType: 'String',
          StringValue: 'shape-file',
        },
      },
    };

    await sqs.sendMessage(sqsParams).promise();

    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        success: true,
        uploadId,
        message: 'Shape file uploaded successfully (internal)',
        location: `s3://${s3Params.Bucket}/${s3Key}`,
      }),
    };

  } catch (error) {
    console.error('Error processing internal shapefile upload:', error);
    return {
      statusCode: 500,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        error: 'Failed to process shapefile upload',
        details: error instanceof Error ? error.message : 'Unknown error',
      }),
    };
  }
};