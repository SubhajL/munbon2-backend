import { createClient, RedisClientType } from 'redis';
import { config } from '@config/index';
import { logger } from '@utils/logger';

class CacheService {
  private client: RedisClientType | null = null;
  private isConnected = false;

  async connect(): Promise<void> {
    if (this.isConnected) return;

    try {
      this.client = createClient({
        socket: {
          host: config.redis.host,
          port: config.redis.port,
        },
        database: config.redis.db,
      });

      this.client.on('error', (err) => {
        logger.error('Redis Client Error', err);
      });

      await this.client.connect();
      this.isConnected = true;
      logger.info('Redis connected successfully');
    } catch (error) {
      logger.error('Failed to connect to Redis', error);
      // Don't throw - allow service to work without cache
    }
  }

  async get(key: string): Promise<string | null> {
    if (!this.isConnected || !this.client) return null;

    try {
      return await this.client.get(key);
    } catch (error) {
      logger.error('Redis get error', { key, error });
      return null;
    }
  }

  async set(key: string, value: string, ttl?: number): Promise<void> {
    if (!this.isConnected || !this.client) return;

    try {
      if (ttl) {
        await this.client.setEx(key, ttl, value);
      } else {
        await this.client.set(key, value);
      }
    } catch (error) {
      logger.error('Redis set error', { key, error });
    }
  }

  async delete(key: string): Promise<void> {
    if (!this.isConnected || !this.client) return;

    try {
      await this.client.del(key);
    } catch (error) {
      logger.error('Redis delete error', { key, error });
    }
  }

  async disconnect(): Promise<void> {
    if (this.client && this.isConnected) {
      await this.client.quit();
      this.isConnected = false;
      logger.info('Redis disconnected');
    }
  }
}

export const cacheService = new CacheService();

// Initialize cache connection
cacheService.connect().catch(err => {
  logger.error('Failed to initialize cache', err);
});