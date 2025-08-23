"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.startMetricsCollection = exports.metricsCollector = void 0;
const redis_1 = require("../config/redis");
const logger_1 = require("./logger");
class MetricsCollector {
    redis = (0, redis_1.getRedisClient)();
    metricsInterval = null;
    start(intervalMs = 30000) {
        if (this.metricsInterval) {
            logger_1.logger.warn('Metrics collection already started');
            return;
        }
        this.metricsInterval = setInterval(() => {
            this.collectMetrics().catch(error => {
                logger_1.logger.error(error, 'Failed to collect metrics');
            });
        }, intervalMs);
        logger_1.logger.info('Metrics collection started');
    }
    stop() {
        if (this.metricsInterval) {
            clearInterval(this.metricsInterval);
            this.metricsInterval = null;
            logger_1.logger.info('Metrics collection stopped');
        }
    }
    async collectMetrics() {
        try {
            const metrics = {
                totalFields: await this.countTotalFields(),
                activeIrrigations: await this.countActiveIrrigations(),
                waterSavedLiters: await this.calculateWaterSaved(),
                averageWaterLevel: await this.getAverageWaterLevel(),
                sensorFailures: await this.countSensorFailures(),
                irrigationCycles: await this.countIrrigationCycles(),
            };
            await this.redis.hset('awd:metrics:current', {
                ...metrics,
                timestamp: new Date().toISOString(),
            });
            logger_1.logger.debug({ metrics }, 'Metrics collected');
        }
        catch (error) {
            logger_1.logger.error(error, 'Error collecting metrics');
        }
    }
    async countTotalFields() {
        return 0;
    }
    async countActiveIrrigations() {
        const active = await this.redis.scard('awd:irrigation:active');
        return active || 0;
    }
    async calculateWaterSaved() {
        return 0;
    }
    async getAverageWaterLevel() {
        return 0;
    }
    async countSensorFailures() {
        return 0;
    }
    async countIrrigationCycles() {
        return 0;
    }
    async getMetrics() {
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
        }
        catch (error) {
            logger_1.logger.error(error, 'Failed to get metrics');
            return null;
        }
    }
}
exports.metricsCollector = new MetricsCollector();
const startMetricsCollection = () => {
    const interval = parseInt(process.env.HEALTH_CHECK_INTERVAL || '30000');
    exports.metricsCollector.start(interval);
};
exports.startMetricsCollection = startMetricsCollection;
//# sourceMappingURL=metrics.js.map