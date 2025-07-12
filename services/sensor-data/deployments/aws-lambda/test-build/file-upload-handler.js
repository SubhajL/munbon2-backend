"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.handler = void 0;
const AWS = require("aws-sdk");
const uuid_1 = require("uuid");
const Busboy = require('busboy');
const s3 = new AWS.S3();
const sqs = new AWS.SQS();
const VALID_TOKEN = 'munbon-ridms-shape';
const SHAPE_FILE_BUCKET = process.env.SHAPE_FILE_BUCKET || 'munbon-shape-files';
const SQS_QUEUE_URL = process.env.SQS_QUEUE_URL;
/**
 * Lambda handler for direct shape file uploads
 * Endpoint: POST /api/v1/rid-ms/upload
 * Content-Type: multipart/form-data
 */
const handler = async (event) => {
    console.log('File upload handler triggered');
    try {
        // Validate authorization token
        const authHeader = event.headers.Authorization || event.headers.authorization;
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return {
                statusCode: 401,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ error: 'Missing authorization header' })
            };
        }
        const token = authHeader.substring(7);
        if (token !== VALID_TOKEN) {
            return {
                statusCode: 403,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ error: 'Invalid authorization token' })
            };
        }
        // Parse multipart form data
        const contentType = event.headers['content-type'] || event.headers['Content-Type'];
        if (!contentType || !contentType.includes('multipart/form-data')) {
            return {
                statusCode: 400,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ error: 'Content-Type must be multipart/form-data' })
            };
        }
        // API Gateway sends binary data as base64 when isBase64Encoded is true
        const bodyBuffer = event.isBase64Encoded
            ? Buffer.from(event.body || '', 'base64')
            : Buffer.from(event.body || '', 'utf8');
        // Parse the multipart form
        const result = await parseMultipartForm(bodyBuffer, contentType);
        if (!result.file) {
            return {
                statusCode: 400,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ error: 'No file uploaded' })
            };
        }
        // Validate file is a zip
        if (!result.fileName.toLowerCase().endsWith('.zip')) {
            return {
                statusCode: 400,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ error: 'Only .zip files are accepted' })
            };
        }
        // Generate unique ID for this upload
        const uploadId = (0, uuid_1.v4)();
        const timestamp = new Date().toISOString();
        const uploadDate = timestamp.split('T')[0];
        // Upload to S3
        const s3Key = `shape-files/${uploadDate}/${uploadId}/${result.fileName}`;
        await s3.putObject({
            Bucket: SHAPE_FILE_BUCKET,
            Key: s3Key,
            Body: result.file,
            ContentType: 'application/zip',
            Metadata: {
                uploadId,
                originalFileName: result.fileName,
                waterDemandMethod: result.metadata.waterDemandMethod || 'RID-MS',
                processingInterval: result.metadata.processingInterval || 'weekly',
                uploadedAt: timestamp,
                uploadedBy: result.metadata.uploadedBy || 'api-upload',
                zone: result.metadata.zone || '',
                description: result.metadata.description || ''
            }
        }).promise();
        console.log(`File uploaded to S3: ${s3Key}`);
        // Send message to SQS for processing
        const sqsMessage = {
            type: 'shape-file',
            uploadId,
            s3Bucket: SHAPE_FILE_BUCKET,
            s3Key,
            fileName: result.fileName,
            waterDemandMethod: result.metadata.waterDemandMethod || 'RID-MS',
            processingInterval: result.metadata.processingInterval || 'weekly',
            metadata: result.metadata,
            uploadedAt: timestamp,
            source: 'file-upload-api'
        };
        await sqs.sendMessage({
            QueueUrl: SQS_QUEUE_URL,
            MessageBody: JSON.stringify(sqsMessage),
            MessageAttributes: {
                uploadId: {
                    DataType: 'String',
                    StringValue: uploadId
                },
                dataType: {
                    DataType: 'String',
                    StringValue: 'shape-file'
                }
            }
        }).promise();
        console.log(`Message sent to SQS for upload: ${uploadId}`);
        // Return success response
        return {
            statusCode: 200,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                success: true,
                uploadId,
                message: 'Shape file uploaded successfully and queued for processing',
                fileName: result.fileName,
                fileSize: result.file.length,
                uploadedAt: timestamp
            })
        };
    }
    catch (error) {
        console.error('Error processing file upload:', error);
        return {
            statusCode: 500,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                error: 'Internal server error',
                message: error instanceof Error ? error.message : 'Unknown error'
            })
        };
    }
};
exports.handler = handler;
/**
 * Parse multipart form data
 */
function parseMultipartForm(buffer, contentType) {
    return new Promise((resolve, reject) => {
        const busboy = new Busboy({ headers: { 'content-type': contentType } });
        let file;
        let fileName = '';
        const metadata = {};
        const chunks = [];
        busboy.on('file', (fieldname, stream, filename) => {
            console.log(`Processing file field: ${fieldname}, filename: ${filename}`);
            fileName = filename;
            stream.on('data', (data) => {
                chunks.push(data);
            });
            stream.on('end', () => {
                file = Buffer.concat(chunks);
                console.log(`File processed: ${filename}, size: ${file.length} bytes`);
            });
        });
        busboy.on('field', (fieldname, value) => {
            console.log(`Processing field: ${fieldname} = ${value}`);
            switch (fieldname) {
                case 'waterDemandMethod':
                    if (['RID-MS', 'ROS', 'AWD'].includes(value)) {
                        metadata.waterDemandMethod = value;
                    }
                    break;
                case 'processingInterval':
                    if (['daily', 'weekly', 'bi-weekly'].includes(value)) {
                        metadata.processingInterval = value;
                    }
                    break;
                case 'zone':
                    metadata.zone = value;
                    break;
                case 'uploadedBy':
                    metadata.uploadedBy = value;
                    break;
                case 'description':
                    metadata.description = value;
                    break;
            }
        });
        busboy.on('finish', () => {
            resolve({ file, fileName, metadata });
        });
        busboy.on('error', (error) => {
            reject(error);
        });
        busboy.write(buffer);
        busboy.end();
    });
}
