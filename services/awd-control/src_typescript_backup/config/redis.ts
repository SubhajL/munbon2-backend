import Redis from 'ioredis';
import { logger } from '../utils/logger';

let redisClient: Redis;
let redisSubscriber: Redis;

export const initializeRedis = async (): Promise<void> => {
  try {
    const redisConfig = {
      host: process.env.REDIS_HOST || 'localhost',
      port: parseInt(process.env.REDIS_PORT || '6379'),
      db: parseInt(process.env.REDIS_DB || '11'),
      password: process.env.REDIS_PASSWORD,
      retryStrategy: (times: number) => {
        const delay = Math.min(times * 50, 2000);
        return delay;
      },
      maxRetriesPerRequest: 3,
    };

    // Main Redis client for general operations
    redisClient = new Redis(redisConfig);
    
    // Separate client for pub/sub
    redisSubscriber = new Redis(redisConfig);

    // Handle connection events
    redisClient.on('connect', () => {
      logger.info('Redis client connected');
    });

    redisClient.on('error', (error) => {
      logger.error(error, 'Redis client error');
    });

    redisSubscriber.on('connect', () => {
      logger.info('Redis subscriber connected');
    });

    // Test connection
    await redisClient.ping();
    logger.info('Redis connection established successfully');

    // Initialize keys structure
    await initializeRedisKeys();
  } catch (error) {
    logger.error(error, 'Failed to initialize Redis');
    throw error;
  }
};

export const getRedisClient = (): Redis => {
  if (!redisClient) {
    throw new Error('Redis client not initialized');
  }
  return redisClient;
};

export const getRedisSubscriber = (): Redis => {
  if (!redisSubscriber) {
    throw new Error('Redis subscriber not initialized');
  }
  return redisSubscriber;
};

// Redis key patterns for AWD control
export const RedisKeys = {
  // Field state management
  fieldState: (fieldId: string) => `awd:field:${fieldId}:state`,
  fieldConfig: (fieldId: string) => `awd:field:${fieldId}:config`,
  fieldSensors: (fieldId: string) => `awd:field:${fieldId}:sensors`,
  
  // Sensor data
  sensorReading: (sensorId: string) => `awd:sensor:${sensorId}:latest`,
  sensorStatus: (sensorId: string) => `awd:sensor:${sensorId}:status`,
  
  // Irrigation management
  irrigationQueue: 'awd:irrigation:queue',
  irrigationActive: 'awd:irrigation:active',
  fieldIrrigationHistory: (fieldId: string) => `awd:field:${fieldId}:irrigation:history`,
  
  // Control state
  controlLock: (fieldId: string) => `awd:control:${fieldId}:lock`,
  emergencyOverride: 'awd:emergency:override',
  
  // Analytics
  dailyWaterUsage: (date: string) => `awd:analytics:water:${date}`,
  fieldMetrics: (fieldId: string) => `awd:metrics:${fieldId}`,
  
  // System state
  systemHealth: 'awd:system:health',
  activeAlerts: 'awd:alerts:active',
};

const initializeRedisKeys = async (): Promise<void> => {
  try {
    // Set default system health
    await redisClient.hset(RedisKeys.systemHealth, {
      status: 'healthy',
      lastCheck: new Date().toISOString(),
      activeFields: 0,
      queuedIrrigations: 0,
    });

    logger.info('Redis keys initialized');
  } catch (error) {
    logger.error(error, 'Failed to initialize Redis keys');
    throw error;
  }
};

export const closeRedis = async (): Promise<void> => {
  if (redisClient) {
    redisClient.disconnect();
    logger.info('Redis client disconnected');
  }
  if (redisSubscriber) {
    redisSubscriber.disconnect();
    logger.info('Redis subscriber disconnected');
  }
};