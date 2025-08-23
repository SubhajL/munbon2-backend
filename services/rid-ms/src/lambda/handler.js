"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.processShapeFile = exports.shapeFileExport = exports.shapeFileParcels = exports.shapeFileList = exports.shapeFileMetadata = exports.shapeFileUpload = void 0;
const aws_sdk_1 = __importDefault(require("aws-sdk"));
const uuid_1 = require("uuid");
const shapefile_controller_1 = require("../controllers/shapefile.controller");
const shapefile_service_1 = require("../services/shapefile.service");
const parcel_repository_1 = require("../repository/parcel.repository");
const logger_1 = require("../utils/logger");
const config_1 = require("../config");
const s3 = new aws_sdk_1.default.S3();
const sqs = new aws_sdk_1.default.SQS();
const logger = (0, logger_1.createLogger)('Lambda');
const parcelRepo = new parcel_repository_1.ParcelRepository(config_1.config.database);
const shapeFileService = new shapefile_service_1.ShapeFileService(parcelRepo);
const controller = new shapefile_controller_1.ShapeFileController();
const parseMultipartData = (event) => {
    const boundary = event.headers['content-type'].split('boundary=')[1];
    const body = Buffer.from(event.body, event.isBase64Encoded ? 'base64' : 'utf8');
    const parts = body.toString().split(`--${boundary}`);
    let file = null;
    let filename = '';
    const fields = {};
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
            }
            else {
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
const shapeFileUpload = async (event, context) => {
    try {
        const { file, filename, fields } = parseMultipartData(event);
        const uploadId = (0, uuid_1.v4)();
        const s3Key = `uploads/${uploadId}/${filename}`;
        await s3.putObject({
            Bucket: process.env.S3_BUCKET_NAME,
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
        await sqs.sendMessage({
            QueueUrl: process.env.SQS_QUEUE_URL,
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
    }
    catch (error) {
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
exports.shapeFileUpload = shapeFileUpload;
const shapeFileMetadata = async (event, context) => {
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
    }
    catch (error) {
        logger.error('Error getting shape file metadata:', error);
        return {
            statusCode: 404,
            headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
            body: JSON.stringify({ error: 'Shape file not found' })
        };
    }
};
exports.shapeFileMetadata = shapeFileMetadata;
const shapeFileList = async (event, context) => {
    try {
        const queryParams = event.queryStringParameters || {};
        const options = {
            status: queryParams.status,
            page: parseInt(queryParams.page || '1'),
            limit: parseInt(queryParams.limit || '10'),
            sortBy: queryParams.sortBy || 'uploadDate',
            sortOrder: queryParams.sortOrder || 'desc'
        };
        const result = await shapeFileService.listShapeFiles(options);
        return {
            statusCode: 200,
            headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
            body: JSON.stringify(result)
        };
    }
    catch (error) {
        logger.error('Error listing shape files:', error);
        return {
            statusCode: 500,
            headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
            body: JSON.stringify({ error: 'Failed to list shape files' })
        };
    }
};
exports.shapeFileList = shapeFileList;
const shapeFileParcels = async (event, context) => {
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
            waterDemandMethod: queryParams.waterDemandMethod
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
    }
    catch (error) {
        logger.error('Error getting parcels:', error);
        return {
            statusCode: 500,
            headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
            body: JSON.stringify({ error: 'Failed to get parcels' })
        };
    }
};
exports.shapeFileParcels = shapeFileParcels;
const shapeFileExport = async (event, context) => {
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
    }
    catch (error) {
        logger.error('Error exporting shape file:', error);
        return {
            statusCode: 500,
            headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
            body: JSON.stringify({ error: 'Failed to export shape file' })
        };
    }
};
exports.shapeFileExport = shapeFileExport;
const processShapeFile = async (event, context) => {
    for (const record of event.Records) {
        try {
            const message = JSON.parse(record.body);
            const { uploadId, s3Key, filename, metadata } = message;
            logger.info(`Processing shape file: ${uploadId}`);
            const s3Object = await s3.getObject({
                Bucket: process.env.S3_BUCKET_NAME,
                Key: s3Key
            }).promise();
            const fileBuffer = s3Object.Body;
            await shapeFileService.processShapeFile({
                id: uploadId,
                filename,
                buffer: fileBuffer,
                metadata
            });
            await s3.copyObject({
                Bucket: process.env.S3_BUCKET_NAME,
                CopySource: `${process.env.S3_BUCKET_NAME}/${s3Key}`,
                Key: s3Key.replace('uploads/', 'processed/')
            }).promise();
            await s3.deleteObject({
                Bucket: process.env.S3_BUCKET_NAME,
                Key: s3Key
            }).promise();
            logger.info(`Successfully processed shape file: ${uploadId}`);
        }
        catch (error) {
            logger.error('Error processing shape file:', error);
            throw error;
        }
    }
};
exports.processShapeFile = processShapeFile;
//# sourceMappingURL=handler.js.map