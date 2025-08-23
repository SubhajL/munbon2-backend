import { createClient } from 'redis';
import { config } from './index';
import { logger } from '../utils/logger';

class CacheService {
  private client: any;
  private isConnected: boolean = false;

  async initialize(): Promise<void> {
    try {
      this.client = createClient({
        url: config.redis.url,
        password: config.redis.password || undefined,
      });

      this.client.on('error', (err: Error) => {
        logger.error('Redis Client Error:', err);
      });

      await this.client.connect();
      this.isConnected = true;
      logger.info('Cache service connected successfully');
    } catch (error) {
      logger.error('Failed to connect to Redis:', error);
      this.isConnected = false;
    }
  }

  async get(key: string): Promise<any> {
    if (!this.isConnected) return null;
    
    try {
      const value = await this.client.get(key);
      return value ? JSON.parse(value) : null;
    } catch (error) {
      logger.error(`Cache get error for key ${key}:`, error);
      return null;
    }
  }

  async set(key: string, value: any, ttl?: number): Promise<void> {
    if (!this.isConnected) return;
    
    try {
      const serialized = JSON.stringify(value);
      if (ttl) {
        await this.client.setEx(key, ttl, serialized);
      } else {
        await this.client.set(key, serialized);
      }
    } catch (error) {
      logger.error(`Cache set error for key ${key}:`, error);
    }
  }

  async delete(key: string): Promise<void> {
    if (!this.isConnected) return;
    
    try {
      await this.client.del(key);
    } catch (error) {
      logger.error(`Cache delete error for key ${key}:`, error);
    }
  }

  async clearPattern(pattern: string): Promise<void> {
    if (!this.isConnected) return;
    
    try {
      const keys = await this.client.keys(pattern);
      if (keys.length > 0) {
        await this.client.del(keys);
      }
    } catch (error) {
      logger.error(`Cache clear pattern error for ${pattern}:`, error);
    }
  }

  async disconnect(): Promise<void> {
    if (this.client) {
      await this.client.quit();
      this.isConnected = false;
    }
  }
}

export const cacheService = new CacheService();

export async function initializeCache(): Promise<void> {
  await cacheService.initialize();
}