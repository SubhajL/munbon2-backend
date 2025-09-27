const EventEmitter = require('events');
const redisConfig = require('../config/redis');
const logger = require('../utils/logger');
const WaterControlOrchestrator = require('./water-control-orchestrator.service');
const WaterDemandIntegrationService = require('./water-demand-integration.service');

class DemandEventSubscriber extends EventEmitter {
  constructor(orchestratorService, demandService) {
    super();
    this.orchestratorService = orchestratorService || new WaterControlOrchestrator();
    this.demandService = demandService || new WaterDemandIntegrationService();
    this.isSubscribed = false;
    this.isRunning = false;
    this.reconnectTimeout = null;
    this.processingQueue = new Set();
    this.failureCount = new Map();
    this.maxFailures = 3;
    this.demandCache = new Map();
    this.maxRetries = 3;
    this.retryDelay = 1000;
  }

  // Convenience methods for testing
  async start() {
    this.isRunning = true;
    return this.subscribeToEvents();
  }

  async stop() {
    this.isRunning = false;
    return this.unsubscribe();
  }

  async subscribeToEvents() {
    try {
      if (!redisConfig.subscriber) {
        logger.warn('Redis subscriber not available, skipping event subscription');
        return;
      }

      // Subscribe to demand update channel
      await redisConfig.subscriber.subscribe('water:demands:updated', (message) => {
        this.handleMessage('water:demands:updated', message);
      });

      // Subscribe to batch demand channel
      await redisConfig.subscriber.subscribe('water:demands:batch', (message) => {
        this.handleMessage('water:demands:batch', message);
      });

      this.isSubscribed = true;
      logger.info('Successfully subscribed to water demand events');

      // Set up auto-reconnect on connection loss
      redisConfig.subscriber.on('end', () => {
        this.handleConnectionLoss();
      });

    } catch (error) {
      logger.error('Failed to subscribe to events:', error);
      this.handleError(error);
    }
  }

  handleMessage(channel, message) {
    try {
      const eventData = JSON.parse(message);
      logger.info(`Received event on ${channel}:`, {
        event_type: eventData.event_type,
        zone_id: eventData.zone_id,
        timestamp: eventData.timestamp
      });

      // Handle different event types
      switch (eventData.event_type) {
        case 'zone_demand_ready':
          this.handleDemandUpdate(eventData);
          break;
        case 'section_demand_ready':
          // Accumulate section events, process zone when complete
          logger.debug(`Section demand ready: ${eventData.section_id}`);
          break;
        case 'batch_demands_ready':
          this.handleBatchDemands(eventData);
          break;
        default:
          logger.warn(`Unknown event type: ${eventData.event_type}`);
      }

    } catch (error) {
      logger.error('Error handling message:', error);
      this.emit('processing_error', { channel, error });
    }
  }

  async handleDemandUpdate(eventData) {
    const { zone_id, week_start } = eventData;
    const processingKey = `${zone_id}_${week_start}`;

    // Check if already processing this zone/week
    if (this.processingQueue.has(processingKey)) {
      logger.debug(`Already processing ${processingKey}, skipping duplicate event`);
      return;
    }

    try {
      // Mark as processing
      this.processingQueue.add(processingKey);

      // Clear cache to ensure fresh data
      this.clearDemandCache(zone_id, week_start);

      // Trigger orchestration with retry logic
      await this.triggerOrchestration(zone_id, week_start, eventData);

      // Clear from processing queue
      this.processingQueue.delete(processingKey);
      this.failureCount.delete(processingKey);

      logger.info(`Successfully processed demand update for ${zone_id}, week ${week_start}`);

    } catch (error) {
      logger.error(`Failed to process demand update for ${zone_id}:`, error);
      
      // Track failures for circuit breaker
      const failures = (this.failureCount.get(processingKey) || 0) + 1;
      this.failureCount.set(processingKey, failures);

      if (failures >= this.maxFailures) {
        logger.error(`Max failures reached for ${processingKey}, stopping retries`);
        this.processingQueue.delete(processingKey);
        this.emit('max_failures', { zone_id, week_start, error });
      } else {
        // Retry with exponential backoff
        const delay = Math.pow(2, failures) * 1000;
        logger.info(`Retrying ${processingKey} in ${delay}ms (attempt ${failures})`);
        
        setTimeout(() => {
          this.processingQueue.delete(processingKey);
          this.handleDemandUpdate(eventData);
        }, delay);
      }
    }
  }

  async handleBatchDemands(eventData) {
    const { zones, week_start } = eventData;
    logger.info(`Processing batch demands for ${zones.length} zones, week ${week_start}`);

    // Process zones in parallel with concurrency limit
    const concurrency = 3;
    for (let i = 0; i < zones.length; i += concurrency) {
      const batch = zones.slice(i, i + concurrency);
      
      await Promise.allSettled(
        batch.map(zone => this.handleDemandUpdate({
          ...zone,
          event_type: 'zone_demand_ready',
          week_start,
          timestamp: eventData.timestamp
        }))
      );
    }
  }

  clearDemandCache(zoneId, weekStart) {
    if (!this.demandService || !this.demandService.cache) {
      return;
    }

    const cacheKeys = [
      `zone_demands_${zoneId}_${weekStart}`,
      `all_sections_${weekStart}`
    ];

    cacheKeys.forEach(key => {
      if (this.demandService.cache.has(key)) {
        this.demandService.cache.delete(key);
        logger.debug(`Cleared cache key: ${key}`);
      }
    });
  }

  async triggerOrchestration(zoneId, weekStart, eventData) {
    logger.info(`Triggering orchestration for zone ${zoneId}, week ${weekStart}`);

    const options = {
      weekStart,
      source: 'demand_event',
      eventData: {
        total_demand_m3: eventData.total_demand_m3,
        section_count: eventData.section_count
      }
    };

    const result = await this.orchestratorService.orchestrateWaterControl(zoneId, options);
    
    this.emit('orchestration_complete', {
      zone_id: zoneId,
      week_start: weekStart,
      operation_id: result.operation_id,
      gate_count: result.gate_settings?.total_gates || 0
    });

    return result;
  }

  handleConnectionLoss() {
    logger.warn('Redis connection lost, attempting to resubscribe...');
    this.isSubscribed = false;

    // Clear existing timeout
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
    }

    // Attempt reconnection with backoff
    this.reconnectTimeout = setTimeout(() => {
      this.subscribeToEvents();
    }, 5000);
  }

  handleError(error) {
    logger.error('Demand event subscriber error:', error);
    
    // Implement circuit breaker
    if (error.code === 'ECONNREFUSED' || error.code === 'ETIMEDOUT') {
      logger.warn('Redis unavailable, entering degraded mode');
      this.emit('degraded_mode', { reason: 'redis_unavailable' });
    }
  }

  getStatus() {
    return {
      subscribed: this.isSubscribed,
      processingQueue: this.processingQueue.size,
      failureCount: this.failureCount.size,
      redisConnected: redisConfig.isConnected
    };
  }

  async unsubscribe() {
    try {
      if (redisConfig.subscriber && this.isSubscribed) {
        await redisConfig.subscriber.unsubscribe();
        this.isSubscribed = false;
        logger.info('Unsubscribed from demand events');
      }

      if (this.reconnectTimeout) {
        clearTimeout(this.reconnectTimeout);
        this.reconnectTimeout = null;
      }

      this.processingQueue.clear();
      this.failureCount.clear();

    } catch (error) {
      logger.error('Error unsubscribing:', error);
    }
  }
}

module.exports = DemandEventSubscriber;