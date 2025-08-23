import { Request, Response, NextFunction } from 'express';
import { cacheService } from '../services/cache.service';
import { logger } from '../utils/logger';

interface CacheOptions {
  ttl?: number; // Time to live in seconds
  keyGenerator?: (req: Request) => string;
}

export const cacheMiddleware = (options: CacheOptions = {}) => {
  const { ttl = 300, keyGenerator = defaultKeyGenerator } = options;

  return async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    // Only cache GET requests
    if (req.method !== 'GET') {
      next();
      return;
    }

    const key = keyGenerator(req);

    try {
      // Check cache
      const cached = await cacheService.get(key);
      if (cached) {
        logger.debug(`Cache hit: ${key}`);
        res.setHeader('X-Cache', 'HIT');
        res.json(cached);
        return;
      }

      // Store original json method
      const originalJson = res.json;

      // Override json method to cache response
      res.json = function(data: any) {
        res.setHeader('X-Cache', 'MISS');
        
        // Cache the response
        cacheService.set(key, data, ttl)
          .catch(error => logger.error('Cache set error:', error));

        // Call original json method
        return originalJson.call(this, data);
      };

      next();
    } catch (error) {
      logger.error('Cache middleware error:', error);
      next();
    }
  };
};

function defaultKeyGenerator(req: Request): string {
  const { originalUrl, method } = req;
  return `http:${method}:${originalUrl}`;
}