"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.ShapeFileQueueProcessor = void 0;
const AWS = __importStar(require("aws-sdk"));
const shapefile_service_1 = require("../services/shapefile.service");
const logger_1 = require("../utils/logger");
const database_1 = require("../config/database");
class ShapeFileQueueProcessor {
    sqs;
    shapeFileService;
    isRunning = false;
    queueUrl;
    constructor() {
        AWS.config.update({ region: process.env.AWS_REGION || 'ap-southeast-1' });
        this.sqs = new AWS.SQS();
        this.shapeFileService = new shapefile_service_1.ShapeFileService();
        this.queueUrl = process.env.GIS_SQS_QUEUE_URL ||
            `https://sqs.${process.env.AWS_REGION}.amazonaws.com/${process.env.AWS_ACCOUNT_ID}/munbon-gis-shapefile-queue`;
    }
    async start() {
        if (this.isRunning) {
            logger_1.logger.warn('Queue processor is already running');
            return;
        }
        this.isRunning = true;
        logger_1.logger.info('Starting shape file queue processor...', {
            queueUrl: this.queueUrl,
            region: process.env.AWS_REGION
        });
        try {
            await (0, database_1.connectDatabase)();
            logger_1.logger.info('Database connected successfully');
        }
        catch (dbError) {
            logger_1.logger.error('Failed to connect to database', {
                error: dbError instanceof Error ? dbError.message : dbError,
                stack: dbError instanceof Error ? dbError.stack : undefined
            });
            throw dbError;
        }
        logger_1.logger.info('Starting message polling');
        this.pollQueue();
    }
    async stop() {
        logger_1.logger.info('Stopping shape file queue processor...');
        this.isRunning = false;
    }
    async pollQueue() {
        logger_1.logger.info('Starting queue polling', { queueUrl: this.queueUrl });
        while (this.isRunning) {
            try {
                logger_1.logger.debug('Polling for messages...');
                const { Messages } = await this.sqs.receiveMessage({
                    QueueUrl: this.queueUrl,
                    MaxNumberOfMessages: 1,
                    WaitTimeSeconds: 20,
                    VisibilityTimeout: 300,
                }).promise();
                if (Messages && Messages.length > 0) {
                    logger_1.logger.info('Received messages', { count: Messages.length });
                    for (const message of Messages) {
                        await this.processMessage(message);
                    }
                }
                else {
                    logger_1.logger.debug('No messages received');
                }
            }
            catch (error) {
                logger_1.logger.error(`Error polling SQS queue: ${error instanceof Error ? error.message : String(error)}`);
                await new Promise(resolve => setTimeout(resolve, 5000));
            }
        }
    }
    async processMessage(message) {
        const startTime = Date.now();
        try {
            if (!message.Body) {
                throw new Error('Empty message body');
            }
            const messageData = JSON.parse(message.Body);
            logger_1.logger.info(`Processing shape file message - Upload ID: ${messageData.uploadId}, File: ${messageData.fileName}`);
            try {
                await this.shapeFileService.processShapeFileFromQueue(messageData);
            }
            catch (innerError) {
                logger_1.logger.error('Service processing error', {
                    error: innerError instanceof Error ? innerError.message : innerError,
                    stack: innerError instanceof Error ? innerError.stack : undefined
                });
                throw innerError;
            }
            if (message.ReceiptHandle) {
                await this.sqs.deleteMessage({
                    QueueUrl: this.queueUrl,
                    ReceiptHandle: message.ReceiptHandle,
                }).promise();
            }
            const processingTime = Date.now() - startTime;
            logger_1.logger.info(`Shape file processed successfully - Upload ID: ${messageData.uploadId}, Time: ${processingTime}ms`);
        }
        catch (error) {
            logger_1.logger.error(`Failed to process shape file message - Message ID: ${message.MessageId}, Time: ${Date.now() - startTime}ms, Error: ${error instanceof Error ? error.message : String(error)}`);
        }
    }
}
exports.ShapeFileQueueProcessor = ShapeFileQueueProcessor;
if (require.main === module) {
    const processor = new ShapeFileQueueProcessor();
    process.on('SIGTERM', async () => {
        logger_1.logger.info('SIGTERM received, shutting down gracefully...');
        await processor.stop();
        process.exit(0);
    });
    process.on('SIGINT', async () => {
        logger_1.logger.info('SIGINT received, shutting down gracefully...');
        await processor.stop();
        process.exit(0);
    });
    processor.start().catch(error => {
        logger_1.logger.error(`Failed to start queue processor: ${error instanceof Error ? error.message : String(error)}`);
        process.exit(1);
    });
}
//# sourceMappingURL=shapefile-queue-processor.js.map