"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.CacheService = void 0;
const ioredis_1 = __importDefault(require("ioredis"));
const config_1 = require("../config");
const logger_1 = require("../utils/logger");
class CacheService {
    constructor() {
        this.redis = new ioredis_1.default({
            host: config_1.config.redis.host,
            port: config_1.config.redis.port,
            password: config_1.config.redis.password,
            db: config_1.config.redis.db,
            retryStrategy: (times) => {
                const delay = Math.min(times * 50, 2000);
                return delay;
            },
        });
        this.defaultTTL = config_1.config.analytics.cacheTTLSeconds;
        this.redis.on('error', (err) => {
            logger_1.logger.error({ err }, 'Redis error');
        });
        this.redis.on('connect', () => {
            logger_1.logger.info('Connected to Redis');
        });
    }
    async get(key) {
        try {
            const value = await this.redis.get(key);
            if (!value)
                return null;
            return JSON.parse(value);
        }
        catch (error) {
            logger_1.logger.error({ error, key }, 'Failed to get from cache');
            return null;
        }
    }
    async set(key, value, ttl) {
        try {
            const serialized = JSON.stringify(value);
            if (ttl || this.defaultTTL) {
                await this.redis.setex(key, ttl || this.defaultTTL, serialized);
            }
            else {
                await this.redis.set(key, serialized);
            }
        }
        catch (error) {
            logger_1.logger.error({ error, key }, 'Failed to set cache');
        }
    }
    async delete(key) {
        try {
            await this.redis.del(key);
        }
        catch (error) {
            logger_1.logger.error({ error, key }, 'Failed to delete from cache');
        }
    }
    async deletePattern(pattern) {
        try {
            const keys = await this.redis.keys(pattern);
            if (keys.length > 0) {
                await this.redis.del(...keys);
            }
        }
        catch (error) {
            logger_1.logger.error({ error, pattern }, 'Failed to delete pattern from cache');
        }
    }
    async invalidateWeatherCache(location) {
        if (location) {
            await this.deletePattern(`weather:${location.lat}:${location.lng}:*`);
        }
        else {
            await this.deletePattern('weather:*');
        }
    }
    async invalidateForecastCache(location) {
        if (location) {
            await this.deletePattern(`forecast:${location.lat}:${location.lng}:*`);
        }
        else {
            await this.deletePattern('forecast:*');
        }
    }
    async publish(channel, message) {
        try {
            await this.redis.publish(channel, JSON.stringify(message));
        }
        catch (error) {
            logger_1.logger.error({ error, channel }, 'Failed to publish message');
        }
    }
    async subscribe(channel, callback) {
        const subscriber = new ioredis_1.default({
            host: config_1.config.redis.host,
            port: config_1.config.redis.port,
            password: config_1.config.redis.password,
            db: config_1.config.redis.db,
        });
        subscriber.subscribe(channel);
        subscriber.on('message', (ch, message) => {
            if (ch === channel) {
                try {
                    const parsed = JSON.parse(message);
                    callback(parsed);
                }
                catch (error) {
                    logger_1.logger.error({ error, message }, 'Failed to parse message');
                }
            }
        });
    }
    async close() {
        await this.redis.quit();
    }
}
exports.CacheService = CacheService;
//# sourceMappingURL=cache.service.js.map