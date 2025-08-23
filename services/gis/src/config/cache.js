"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.cacheService = void 0;
exports.initializeCache = initializeCache;
const redis_1 = require("redis");
const index_1 = require("./index");
const logger_1 = require("../utils/logger");
class CacheService {
    client;
    isConnected = false;
    async initialize() {
        try {
            this.client = (0, redis_1.createClient)({
                url: index_1.config.redis.url,
                password: index_1.config.redis.password || undefined,
            });
            this.client.on('error', (err) => {
                logger_1.logger.error('Redis Client Error:', err);
            });
            await this.client.connect();
            this.isConnected = true;
            logger_1.logger.info('Cache service connected successfully');
        }
        catch (error) {
            logger_1.logger.error('Failed to connect to Redis:', error);
            this.isConnected = false;
        }
    }
    async get(key) {
        if (!this.isConnected)
            return null;
        try {
            const value = await this.client.get(key);
            return value ? JSON.parse(value) : null;
        }
        catch (error) {
            logger_1.logger.error(`Cache get error for key ${key}:`, error);
            return null;
        }
    }
    async set(key, value, ttl) {
        if (!this.isConnected)
            return;
        try {
            const serialized = JSON.stringify(value);
            if (ttl) {
                await this.client.setEx(key, ttl, serialized);
            }
            else {
                await this.client.set(key, serialized);
            }
        }
        catch (error) {
            logger_1.logger.error(`Cache set error for key ${key}:`, error);
        }
    }
    async delete(key) {
        if (!this.isConnected)
            return;
        try {
            await this.client.del(key);
        }
        catch (error) {
            logger_1.logger.error(`Cache delete error for key ${key}:`, error);
        }
    }
    async clearPattern(pattern) {
        if (!this.isConnected)
            return;
        try {
            const keys = await this.client.keys(pattern);
            if (keys.length > 0) {
                await this.client.del(keys);
            }
        }
        catch (error) {
            logger_1.logger.error(`Cache clear pattern error for ${pattern}:`, error);
        }
    }
    async disconnect() {
        if (this.client) {
            await this.client.quit();
            this.isConnected = false;
        }
    }
}
exports.cacheService = new CacheService();
async function initializeCache() {
    await exports.cacheService.initialize();
}
//# sourceMappingURL=cache.js.map