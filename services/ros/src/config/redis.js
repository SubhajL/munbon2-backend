"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.getRedisClient = exports.connectRedis = void 0;
const redis_1 = require("redis");
const logger_1 = require("../utils/logger");
let redisClient;
const connectRedis = async () => {
    try {
        redisClient = (0, redis_1.createClient)({
            socket: {
                host: process.env.REDIS_HOST || 'localhost',
                port: parseInt(process.env.REDIS_PORT || '6379'),
            },
            password: process.env.REDIS_PASSWORD || undefined,
            database: parseInt(process.env.REDIS_DB || '0'),
        });
        redisClient.on('error', (error) => {
            logger_1.logger.error('Redis Client Error:', error);
        });
        redisClient.on('connect', () => {
            logger_1.logger.info('Redis Client Connected');
        });
        redisClient.on('ready', () => {
            logger_1.logger.info('Redis Client Ready');
        });
        await redisClient.connect();
        return redisClient;
    }
    catch (error) {
        logger_1.logger.error('Failed to connect to Redis:', error);
        throw error;
    }
};
exports.connectRedis = connectRedis;
const getRedisClient = () => {
    if (!redisClient) {
        throw new Error('Redis client not initialized');
    }
    return redisClient;
};
exports.getRedisClient = getRedisClient;
//# sourceMappingURL=redis.js.map