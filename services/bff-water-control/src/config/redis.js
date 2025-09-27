const redis = require('redis');
const logger = require('../utils/logger');

class RedisConfig {
  constructor() {
    this.subscriber = null;
    this.publisher = null;
    this.isConnected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.backoffMultiplier = 100;
  }

  async createRedisSubscriber() {
    try {
      // Create subscriber client
      this.subscriber = redis.createClient({
        socket: {
          host: process.env.REDIS_HOST || 'localhost',
          port: parseInt(process.env.REDIS_PORT || '6379'),
          reconnectStrategy: (attempts) => this.reconnectStrategy(attempts)
        },
        password: process.env.REDIS_PASSWORD || undefined
      });

      // Create publisher client
      this.publisher = this.subscriber.duplicate();

      // Set up event handlers for subscriber
      this.subscriber.on('connect', () => {
        this.isConnected = true;
        this.reconnectAttempts = 0;
        logger.info('Redis subscriber connected successfully');
      });

      this.subscriber.on('error', (err) => this.handleRedisError(err));
      this.subscriber.on('end', () => {
        this.isConnected = false;
        logger.warn('Redis subscriber connection closed');
      });

      // Set up event handlers for publisher
      this.publisher.on('connect', () => {
        logger.info('Redis publisher connected successfully');
      });

      this.publisher.on('error', (err) => {
        logger.error('Redis publisher error:', err);
      });

      // Connect both clients
      await Promise.all([
        this.subscriber.connect(),
        this.publisher.connect()
      ]);

      this.isConnected = true;
      return { subscriber: this.subscriber, publisher: this.publisher };

    } catch (error) {
      logger.error('Failed to create Redis clients:', error);
      this.isConnected = false;
      throw error;
    }
  }

  reconnectStrategy(attempts) {
    this.reconnectAttempts = attempts;
    
    if (attempts > this.maxReconnectAttempts) {
      logger.error(`Redis reconnection failed after ${attempts} attempts`);
      return false; // Stop reconnecting
    }

    const delay = Math.min(attempts * this.backoffMultiplier, 3000);
    logger.info(`Redis reconnecting... attempt ${attempts}, delay ${delay}ms`);
    return delay;
  }

  handleRedisError(error) {
    logger.error('Redis error:', error.message);
    
    // Implement circuit breaker pattern
    if (error.code === 'ECONNREFUSED' || error.code === 'ENOTFOUND') {
      logger.warn('Redis server not reachable, operating in degraded mode');
      this.isConnected = false;
    }
  }

  getStatus() {
    return {
      connected: this.isConnected,
      subscriberReady: this.subscriber?.isReady || false,
      publisherReady: this.publisher?.isReady || false,
      reconnectAttempts: this.reconnectAttempts
    };
  }

  async disconnect() {
    try {
      if (this.subscriber) {
        await this.subscriber.quit();
        this.subscriber = null;
      }
      if (this.publisher) {
        await this.publisher.quit();
        this.publisher = null;
      }
      this.isConnected = false;
      logger.info('Redis clients disconnected');
    } catch (error) {
      logger.error('Error disconnecting Redis:', error);
    }
  }
}

module.exports = new RedisConfig();