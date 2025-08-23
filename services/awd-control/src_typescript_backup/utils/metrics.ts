import { getRedisClient } from '../config/redis';
import { logger } from './logger';

interface AWDMetrics {
  totalFields: number;
  activeIrrigations: number;
  waterSavedLiters: number;
  averageWaterLevel: number;
  sensorFailures: number;
  irrigationCycles: number;
}

class MetricsCollector {
  private redis = getRedisClient();
  private metricsInterval: NodeJS.Timeout | null = null;

  start(intervalMs: number = 30000): void {
    if (this.metricsInterval) {
      logger.warn('Metrics collection already started');
      return;
    }

    this.metricsInterval = setInterval(() => {
      this.collectMetrics().catch(error => {
        logger.error(error, 'Failed to collect metrics');
      });
    }, intervalMs);

    logger.info('Metrics collection started');
  }

  stop(): void {
    if (this.metricsInterval) {
      clearInterval(this.metricsInterval);
      this.metricsInterval = null;
      logger.info('Metrics collection stopped');
    }
  }

  private async collectMetrics(): Promise<void> {
    try {
      // Collect various metrics
      const metrics: AWDMetrics = {
        totalFields: await this.countTotalFields(),
        activeIrrigations: await this.countActiveIrrigations(),
        waterSavedLiters: await this.calculateWaterSaved(),
        averageWaterLevel: await this.getAverageWaterLevel(),
        sensorFailures: await this.countSensorFailures(),
        irrigationCycles: await this.countIrrigationCycles(),
      };

      // Store metrics in Redis
      await this.redis.hset('awd:metrics:current', {
        ...metrics,
        timestamp: new Date().toISOString(),
      });

      logger.debug({ metrics }, 'Metrics collected');
    } catch (error) {
      logger.error(error, 'Error collecting metrics');
    }
  }

  private async countTotalFields(): Promise<number> {
    // Implementation will be added with field management
    return 0;
  }

  private async countActiveIrrigations(): Promise<number> {
    const active = await this.redis.scard('awd:irrigation:active');
    return active || 0;
  }

  private async calculateWaterSaved(): Promise<number> {
    // Implementation will be added with analytics module
    return 0;
  }

  private async getAverageWaterLevel(): Promise<number> {
    // Implementation will be added with sensor data integration
    return 0;
  }

  private async countSensorFailures(): Promise<number> {
    // Implementation will be added with sensor management
    return 0;
  }

  private async countIrrigationCycles(): Promise<number> {
    // Implementation will be added with irrigation tracking
    return 0;
  }

  async getMetrics(): Promise<AWDMetrics | null> {
    try {
      const metrics = await this.redis.hgetall('awd:metrics:current');
      if (!metrics || Object.keys(metrics).length === 0) {
        return null;
      }

      return {
        totalFields: parseInt(metrics.totalFields || '0'),
        activeIrrigations: parseInt(metrics.activeIrrigations || '0'),
        waterSavedLiters: parseFloat(metrics.waterSavedLiters || '0'),
        averageWaterLevel: parseFloat(metrics.averageWaterLevel || '0'),
        sensorFailures: parseInt(metrics.sensorFailures || '0'),
        irrigationCycles: parseInt(metrics.irrigationCycles || '0'),
      };
    } catch (error) {
      logger.error(error, 'Failed to get metrics');
      return null;
    }
  }
}

export const metricsCollector = new MetricsCollector();

export const startMetricsCollection = (): void => {
  const interval = parseInt(process.env.HEALTH_CHECK_INTERVAL || '30000');
  metricsCollector.start(interval);
};