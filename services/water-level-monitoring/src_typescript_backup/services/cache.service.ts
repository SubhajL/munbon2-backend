import Redis from 'ioredis';
import { config } from '../config';
import { logger } from '../utils/logger';

export class CacheService {
  private redis: Redis;
  private defaultTTL: number;

  constructor() {
    this.redis = new Redis({
      host: config.redis.host,
      port: config.redis.port,
      password: config.redis.password,
      db: config.redis.db,
      retryStrategy: (times) => {
        const delay = Math.min(times * 50, 2000);
        return delay;
      },
    });
    
    this.defaultTTL = config.analytics.cacheTTLSeconds;
    
    this.redis.on('error', (err) => {
      logger.error({ err }, 'Redis error');
    });
    
    this.redis.on('connect', () => {
      logger.info('Connected to Redis');
    });
  }

  async get<T>(key: string): Promise<T | null> {
    try {
      const value = await this.redis.get(key);
      if (!value) return null;
      return JSON.parse(value);
    } catch (error) {
      logger.error({ error, key }, 'Failed to get from cache');
      return null;
    }
  }

  async set(key: string, value: any, ttl?: number): Promise<void> {
    try {
      const serialized = JSON.stringify(value);
      if (ttl || this.defaultTTL) {
        await this.redis.setex(key, ttl || this.defaultTTL, serialized);
      } else {
        await this.redis.set(key, serialized);
      }
    } catch (error) {
      logger.error({ error, key }, 'Failed to set cache');
    }
  }

  async delete(key: string): Promise<void> {
    try {
      await this.redis.del(key);
    } catch (error) {
      logger.error({ error, key }, 'Failed to delete from cache');
    }
  }

  async deletePattern(pattern: string): Promise<void> {
    try {
      const keys = await this.redis.keys(pattern);
      if (keys.length > 0) {
        await this.redis.del(...keys);
      }
    } catch (error) {
      logger.error({ error, pattern }, 'Failed to delete pattern from cache');
    }
  }

  async invalidateSensorCache(sensorId: string): Promise<void> {
    await this.deletePattern(`water-level:${sensorId}:*`);
  }

  async publish(channel: string, message: any): Promise<void> {
    try {
      await this.redis.publish(channel, JSON.stringify(message));
    } catch (error) {
      logger.error({ error, channel }, 'Failed to publish message');
    }
  }

  async subscribe(channel: string, callback: (message: any) => void): Promise<void> {
    const subscriber = new Redis({
      host: config.redis.host,
      port: config.redis.port,
      password: config.redis.password,
      db: config.redis.db,
    });
    
    subscriber.subscribe(channel);
    
    subscriber.on('message', (ch, message) => {
      if (ch === channel) {
        try {
          const parsed = JSON.parse(message);
          callback(parsed);
        } catch (error) {
          logger.error({ error, message }, 'Failed to parse message');
        }
      }
    });
  }

  async close(): Promise<void> {
    await this.redis.quit();
  }
}