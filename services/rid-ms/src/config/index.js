"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.config = void 0;
const dotenv_1 = __importDefault(require("dotenv"));
dotenv_1.default.config();
exports.config = {
    env: process.env.NODE_ENV || 'development',
    port: parseInt(process.env.PORT || '3048', 10),
    serviceName: process.env.SERVICE_NAME || 'rid-ms-service',
    database: {
        host: process.env.POSTGRES_HOST || 'localhost',
        port: parseInt(process.env.POSTGRES_PORT || '5432', 10),
        database: process.env.POSTGRES_DB || 'munbon_gis',
        user: process.env.POSTGRES_USER || 'postgres',
        password: process.env.POSTGRES_PASSWORD || 'postgres',
        maxConnections: 20,
        idleTimeoutMillis: 30000,
    },
    redis: {
        host: process.env.REDIS_HOST || 'localhost',
        port: parseInt(process.env.REDIS_PORT || '6379', 10),
        password: process.env.REDIS_PASSWORD || '',
    },
    kafka: {
        brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
        clientId: process.env.KAFKA_CLIENT_ID || 'rid-ms-service',
        groupId: process.env.KAFKA_GROUP_ID || 'rid-ms-group',
        topics: {
            shapeFileProcessed: 'rid-ms.shapefile.processed',
            waterDemandUpdated: 'rid-ms.water-demand.updated',
            processingError: 'rid-ms.processing.error',
        },
    },
    fileProcessing: {
        uploadDir: process.env.UPLOAD_DIR || '/tmp/rid-ms/uploads',
        processedDir: process.env.PROCESSED_DIR || '/tmp/rid-ms/processed',
        archiveDir: process.env.ARCHIVE_DIR || '/tmp/rid-ms/archive',
        maxFileSize: parseInt(process.env.MAX_FILE_SIZE || '104857600', 10),
        allowedFileTypes: (process.env.ALLOWED_FILE_TYPES || '.zip,.shp,.dbf,.shx,.prj').split(','),
        retentionDays: parseInt(process.env.SHAPE_FILE_RETENTION_DAYS || '30', 10),
        batchSize: parseInt(process.env.PROCESS_BATCH_SIZE || '100', 10),
    },
    waterDemand: {
        defaultMethod: process.env.DEFAULT_WATER_DEMAND_METHOD || 'RID-MS',
        updateInterval: process.env.WATER_DEMAND_UPDATE_INTERVAL || 'weekly',
        coordinateSystem: process.env.COORDINATE_SYSTEM || 'EPSG:32648',
    },
    api: {
        prefix: process.env.API_PREFIX || '/api/v1',
        rateLimitWindow: parseInt(process.env.API_RATE_LIMIT_WINDOW || '15', 10),
        rateLimitMaxRequests: parseInt(process.env.API_RATE_LIMIT_MAX_REQUESTS || '100', 10),
    },
    logging: {
        level: process.env.LOG_LEVEL || 'info',
        file: process.env.LOG_FILE || '/var/log/rid-ms/service.log',
    },
    jobs: {
        shapeFileCheckCron: process.env.SHAPE_FILE_CHECK_CRON || '0 6 * * *',
        cleanupCron: process.env.CLEANUP_CRON || '0 2 * * 0',
    },
    integrations: {
        gisService: {
            url: process.env.GIS_SERVICE_URL || 'http://localhost:3006',
            apiKey: process.env.GIS_SERVICE_API_KEY || '',
        },
        waterDemandService: {
            url: process.env.WATER_DEMAND_SERVICE_URL || 'http://localhost:3050',
            apiKey: process.env.WATER_DEMAND_SERVICE_API_KEY || '',
        },
    },
};
//# sourceMappingURL=index.js.map