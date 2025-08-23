"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.closeRedis = exports.RedisKeys = exports.getRedisSubscriber = exports.getRedisClient = exports.initializeRedis = void 0;
const ioredis_1 = __importDefault(require("ioredis"));
const logger_1 = require("../utils/logger");
let redisClient;
let redisSubscriber;
const initializeRedis = async () => {
    try {
        const redisConfig = {
            host: process.env.REDIS_HOST || 'localhost',
            port: parseInt(process.env.REDIS_PORT || '6379'),
            db: parseInt(process.env.REDIS_DB || '11'),
            password: process.env.REDIS_PASSWORD,
            retryStrategy: (times) => {
                const delay = Math.min(times * 50, 2000);
                return delay;
            },
            maxRetriesPerRequest: 3,
        };
        redisClient = new ioredis_1.default(redisConfig);
        redisSubscriber = new ioredis_1.default(redisConfig);
        redisClient.on('connect', () => {
            logger_1.logger.info('Redis client connected');
        });
        redisClient.on('error', (error) => {
            logger_1.logger.error(error, 'Redis client error');
        });
        redisSubscriber.on('connect', () => {
            logger_1.logger.info('Redis subscriber connected');
        });
        await redisClient.ping();
        logger_1.logger.info('Redis connection established successfully');
        await initializeRedisKeys();
    }
    catch (error) {
        logger_1.logger.error(error, 'Failed to initialize Redis');
        throw error;
    }
};
exports.initializeRedis = initializeRedis;
const getRedisClient = () => {
    if (!redisClient) {
        throw new Error('Redis client not initialized');
    }
    return redisClient;
};
exports.getRedisClient = getRedisClient;
const getRedisSubscriber = () => {
    if (!redisSubscriber) {
        throw new Error('Redis subscriber not initialized');
    }
    return redisSubscriber;
};
exports.getRedisSubscriber = getRedisSubscriber;
exports.RedisKeys = {
    fieldState: (fieldId) => `awd:field:${fieldId}:state`,
    fieldConfig: (fieldId) => `awd:field:${fieldId}:config`,
    fieldSensors: (fieldId) => `awd:field:${fieldId}:sensors`,
    sensorReading: (sensorId) => `awd:sensor:${sensorId}:latest`,
    sensorStatus: (sensorId) => `awd:sensor:${sensorId}:status`,
    irrigationQueue: 'awd:irrigation:queue',
    irrigationActive: 'awd:irrigation:active',
    fieldIrrigationHistory: (fieldId) => `awd:field:${fieldId}:irrigation:history`,
    controlLock: (fieldId) => `awd:control:${fieldId}:lock`,
    emergencyOverride: 'awd:emergency:override',
    dailyWaterUsage: (date) => `awd:analytics:water:${date}`,
    fieldMetrics: (fieldId) => `awd:metrics:${fieldId}`,
    systemHealth: 'awd:system:health',
    activeAlerts: 'awd:alerts:active',
};
const initializeRedisKeys = async () => {
    try {
        await redisClient.hset(exports.RedisKeys.systemHealth, {
            status: 'healthy',
            lastCheck: new Date().toISOString(),
            activeFields: 0,
            queuedIrrigations: 0,
        });
        logger_1.logger.info('Redis keys initialized');
    }
    catch (error) {
        logger_1.logger.error(error, 'Failed to initialize Redis keys');
        throw error;
    }
};
const closeRedis = async () => {
    if (redisClient) {
        redisClient.disconnect();
        logger_1.logger.info('Redis client disconnected');
    }
    if (redisSubscriber) {
        redisSubscriber.disconnect();
        logger_1.logger.info('Redis subscriber disconnected');
    }
};
exports.closeRedis = closeRedis;
//# sourceMappingURL=redis.js.map