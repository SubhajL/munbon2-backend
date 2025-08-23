"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.optionsHandler = exports.handler = void 0;
const aws_sdk_1 = __importDefault(require("aws-sdk"));
const uuid_1 = require("uuid");
const s3 = new aws_sdk_1.default.S3();
const sqs = new aws_sdk_1.default.SQS();
const QUEUE_URL = process.env.QUEUE_URL || '';
const BUCKET_NAME = process.env.BUCKET_NAME || 'rid-ms-uploads';
const EXPECTED_TOKEN = process.env.API_TOKEN || 'munbon-ridms-shape';
const handler = async (event) => {
    console.log('Received event:', JSON.stringify(event, null, 2));
    try {
        const authHeader = event.headers.Authorization || event.headers.authorization;
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return {
                statusCode: 401,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                body: JSON.stringify({ error: 'Missing authorization header' }),
            };
        }
        const token = authHeader.substring(7);
        if (token !== EXPECTED_TOKEN) {
            console.error('Invalid token provided');
            return {
                statusCode: 403,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                body: JSON.stringify({ error: 'Invalid authorization token' }),
            };
        }
        if (!event.body) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                body: JSON.stringify({ error: 'Request body is required' }),
            };
        }
        let requestData;
        try {
            requestData = JSON.parse(event.body);
        }
        catch (error) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                body: JSON.stringify({ error: 'Invalid JSON in request body' }),
            };
        }
        if (!requestData.fileName || !requestData.fileContent) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                body: JSON.stringify({
                    error: 'Missing required fields: fileName and fileContent'
                }),
            };
        }
        if (!requestData.fileName.toLowerCase().endsWith('.zip')) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                body: JSON.stringify({
                    error: 'Only .zip files are accepted'
                }),
            };
        }
        const uploadId = (0, uuid_1.v4)();
        const timestamp = new Date().toISOString();
        let fileBuffer;
        try {
            fileBuffer = Buffer.from(requestData.fileContent, 'base64');
        }
        catch (error) {
            return {
                statusCode: 400,
                headers: {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                body: JSON.stringify({
                    error: 'Invalid base64 encoded file content'
                }),
            };
        }
        const s3Key = `uploads/${new Date().toISOString().split('T')[0]}/${uploadId}/${requestData.fileName}`;
        await s3.putObject({
            Bucket: BUCKET_NAME,
            Key: s3Key,
            Body: fileBuffer,
            ContentType: 'application/zip',
            Metadata: {
                uploadId,
                originalFileName: requestData.fileName,
                waterDemandMethod: requestData.waterDemandMethod || 'RID-MS',
                processingInterval: requestData.processingInterval || 'weekly',
                uploadedAt: timestamp,
                ...(requestData.metadata || {}),
            },
        }).promise();
        console.log(`File uploaded to S3: ${s3Key}`);
        const sqsMessage = {
            uploadId,
            s3Bucket: BUCKET_NAME,
            s3Key,
            fileName: requestData.fileName,
            waterDemandMethod: requestData.waterDemandMethod || 'RID-MS',
            processingInterval: requestData.processingInterval || 'weekly',
            metadata: requestData.metadata,
            uploadedAt: timestamp,
            source: 'api-gateway',
        };
        await sqs.sendMessage({
            QueueUrl: QUEUE_URL,
            MessageBody: JSON.stringify(sqsMessage),
            MessageAttributes: {
                uploadId: {
                    DataType: 'String',
                    StringValue: uploadId,
                },
                waterDemandMethod: {
                    DataType: 'String',
                    StringValue: requestData.waterDemandMethod || 'RID-MS',
                },
            },
        }).promise();
        console.log(`Message sent to SQS for upload: ${uploadId}`);
        return {
            statusCode: 200,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            body: JSON.stringify({
                success: true,
                uploadId,
                message: 'Shape file uploaded successfully and queued for processing',
                fileName: requestData.fileName,
                uploadedAt: timestamp,
            }),
        };
    }
    catch (error) {
        console.error('Error processing request:', error);
        return {
            statusCode: 500,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            body: JSON.stringify({
                error: 'Internal server error',
                message: error instanceof Error ? error.message : 'Unknown error',
            }),
        };
    }
};
exports.handler = handler;
const optionsHandler = async (event) => {
    return {
        statusCode: 200,
        headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '86400',
        },
        body: '',
    };
};
exports.optionsHandler = optionsHandler;
//# sourceMappingURL=api-gateway-handler.js.map