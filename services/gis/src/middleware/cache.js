"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.cacheMiddleware = void 0;
const cache_service_1 = require("../services/cache.service");
const logger_1 = require("../utils/logger");
const cacheMiddleware = (options = {}) => {
    const { ttl = 300, keyGenerator = defaultKeyGenerator } = options;
    return async (req, res, next) => {
        if (req.method !== 'GET') {
            next();
            return;
        }
        const key = keyGenerator(req);
        try {
            const cached = await cache_service_1.cacheService.get(key);
            if (cached) {
                logger_1.logger.debug(`Cache hit: ${key}`);
                res.setHeader('X-Cache', 'HIT');
                res.json(cached);
                return;
            }
            const originalJson = res.json;
            res.json = function (data) {
                res.setHeader('X-Cache', 'MISS');
                cache_service_1.cacheService.set(key, data, ttl)
                    .catch(error => logger_1.logger.error('Cache set error:', error));
                return originalJson.call(this, data);
            };
            next();
        }
        catch (error) {
            logger_1.logger.error('Cache middleware error:', error);
            next();
        }
    };
};
exports.cacheMiddleware = cacheMiddleware;
function defaultKeyGenerator(req) {
    const { originalUrl, method } = req;
    return `http:${method}:${originalUrl}`;
}
//# sourceMappingURL=cache.js.map