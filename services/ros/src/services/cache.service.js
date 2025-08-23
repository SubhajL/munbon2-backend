"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.cacheService = void 0;
const redis_1 = require("redis");
const index_1 = require("@config/index");
const logger_1 = require("@utils/logger");
class CacheService {
    client = null;
    isConnected = false;
    async connect() {
        if (this.isConnected)
            return;
        try {
            this.client = (0, redis_1.createClient)({
                socket: {
                    host: index_1.config.redis.host,
                    port: index_1.config.redis.port,
                },
                database: index_1.config.redis.db,
            });
            this.client.on('error', (err) => {
                logger_1.logger.error('Redis Client Error', err);
            });
            await this.client.connect();
            this.isConnected = true;
            logger_1.logger.info('Redis connected successfully');
        }
        catch (error) {
            logger_1.logger.error('Failed to connect to Redis', error);
            // Don't throw - allow service to work without cache
        }
    }
    async get(key) {
        if (!this.isConnected || !this.client)
            return null;
        try {
            return await this.client.get(key);
        }
        catch (error) {
            logger_1.logger.error('Redis get error', { key, error });
            return null;
        }
    }
    async set(key, value, ttl) {
        if (!this.isConnected || !this.client)
            return;
        try {
            if (ttl) {
                await this.client.setEx(key, ttl, value);
            }
            else {
                await this.client.set(key, value);
            }
        }
        catch (error) {
            logger_1.logger.error('Redis set error', { key, error });
        }
    }
    async delete(key) {
        if (!this.isConnected || !this.client)
            return;
        try {
            await this.client.del(key);
        }
        catch (error) {
            logger_1.logger.error('Redis delete error', { key, error });
        }
    }
    async disconnect() {
        if (this.client && this.isConnected) {
            await this.client.quit();
            this.isConnected = false;
            logger_1.logger.info('Redis disconnected');
        }
    }
}
exports.cacheService = new CacheService();
// Initialize cache connection
exports.cacheService.connect().catch(err => {
    logger_1.logger.error('Failed to initialize cache', err);
});
//# sourceMappingURL=cache.service.js.map