import { Request, Response, NextFunction } from 'express';
import { RateLimitError } from '../errors';

interface RateLimiterStore {
  increment(key: string): Promise<{ count: number; ttl: number }>;
  reset(key: string): Promise<void>;
}

// In-memory store (for development/single instance)
class InMemoryStore implements RateLimiterStore {
  private store = new Map<string, { count: number; resetTime: number }>();
  private windowMs: number;

  constructor(windowMs: number) {
    this.windowMs = windowMs;
  }

  async increment(key: string): Promise<{ count: number; ttl: number }> {
    const now = Date.now();
    const record = this.store.get(key);

    if (!record || record.resetTime < now) {
      const resetTime = now + this.windowMs;
      this.store.set(key, { count: 1, resetTime });
      return { count: 1, ttl: this.windowMs };
    }

    record.count++;
    const ttl = record.resetTime - now;
    return { count: record.count, ttl };
  }

  async reset(key: string): Promise<void> {
    this.store.delete(key);
  }
}

export interface RateLimiterOptions {
  windowMs?: number;
  maxRequests?: number;
  keyGenerator?: (req: Request) => string;
  skipSuccessfulRequests?: boolean;
  skipFailedRequests?: boolean;
  store?: RateLimiterStore;
}

export const createRateLimiter = (options: RateLimiterOptions = {}) => {
  const {
    windowMs = 15 * 60 * 1000, // 15 minutes
    maxRequests = 100,
    keyGenerator = (req: Request) => req.ip || 'unknown',
    skipSuccessfulRequests = false,
    skipFailedRequests = false,
    store = new InMemoryStore(windowMs)
  } = options;

  return async (req: Request, res: Response, next: NextFunction): Promise<void> => {
    try {
      const key = keyGenerator(req);
      const { count, ttl } = await store.increment(key);

      // Set rate limit headers
      res.setHeader('X-RateLimit-Limit', maxRequests);
      res.setHeader('X-RateLimit-Remaining', Math.max(0, maxRequests - count));
      res.setHeader('X-RateLimit-Reset', new Date(Date.now() + ttl).toISOString());

      if (count > maxRequests) {
        throw new RateLimitError(
          `Too many requests from ${key}. Please retry after ${Math.ceil(ttl / 1000)} seconds.`
        );
      }

      // Handle skip options
      if (skipSuccessfulRequests || skipFailedRequests) {
        const originalSend = res.send;
        res.send = function(data: any): Response {
          res.send = originalSend;
          
          if (
            (skipSuccessfulRequests && res.statusCode < 400) ||
            (skipFailedRequests && res.statusCode >= 400)
          ) {
            store.reset(key);
          }
          
          return res.send(data);
        };
      }

      next();
    } catch (error) {
      next(error);
    }
  };
};