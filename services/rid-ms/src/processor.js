"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const shape_file_processor_1 = require("./processors/shape-file-processor");
const pino_1 = __importDefault(require("pino"));
const logger = (0, pino_1.default)({ level: process.env.LOG_LEVEL || 'info' });
async function main() {
    logger.info('Starting RID-MS Shape File Processing Service...');
    const requiredEnvVars = [
        'DATABASE_URL',
        'AWS_REGION',
        'SQS_QUEUE_URL',
        'SHAPE_FILE_BUCKET'
    ];
    for (const envVar of requiredEnvVars) {
        if (!process.env[envVar]) {
            logger.error(`Missing required environment variable: ${envVar}`);
            process.exit(1);
        }
    }
    const processor = new shape_file_processor_1.ShapeFileProcessor();
    process.on('SIGTERM', async () => {
        logger.info('SIGTERM received, shutting down gracefully...');
        await processor.stop();
        process.exit(0);
    });
    process.on('SIGINT', async () => {
        logger.info('SIGINT received, shutting down gracefully...');
        await processor.stop();
        process.exit(0);
    });
    process.on('unhandledRejection', (reason, promise) => {
        logger.error({ reason, promise }, 'Unhandled Rejection');
    });
    process.on('uncaughtException', (error) => {
        logger.error({ error }, 'Uncaught Exception');
        process.exit(1);
    });
    try {
        await processor.start();
    }
    catch (error) {
        logger.error({ error }, 'Failed to start processor');
        process.exit(1);
    }
}
main().catch((error) => {
    logger.error({ error }, 'Unhandled error in main');
    process.exit(1);
});
//# sourceMappingURL=processor.js.map