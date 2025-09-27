const redisConfig = require('../config/redis');
const logger = require('../utils/logger');

class ControlFeedbackPublisher {
  constructor() {
    this.logger = logger.child({ service: 'control-feedback-publisher' });
  }

  async publishExecutionStarted(operationId, zoneId, gateCount) {
    try {
      if (!redisConfig.publisher) {
        this.logger.debug('Redis publisher not available, skipping event');
        return false;
      }

      const event = {
        event_type: 'control_execution_started',
        operation_id: operationId,
        zone_id: zoneId,
        gate_count: gateCount,
        timestamp: new Date().toISOString(),
        status: 'started'
      };

      await redisConfig.publisher.publish(
        'water:controls:status',
        JSON.stringify(event)
      );

      this.logger.info('Published execution started event', {
        operation_id: operationId,
        zone_id: zoneId
      });

      return true;
    } catch (error) {
      this.logger.error('Failed to publish execution started event:', error);
      return false;
    }
  }

  async publishGateUpdated(operationId, gateId, status, details = {}) {
    try {
      if (!redisConfig.publisher) {
        this.logger.debug('Redis publisher not available, skipping event');
        return false;
      }

      const event = {
        event_type: 'gate_control_updated',
        operation_id: operationId,
        gate_id: gateId,
        status,
        command: details.command,
        opening_meters: details.openingMeters,
        flow_rate: details.flowRate,
        timestamp: new Date().toISOString()
      };

      await redisConfig.publisher.publish(
        'water:controls:gates',
        JSON.stringify(event)
      );

      this.logger.debug('Published gate update event', {
        operation_id: operationId,
        gate_id: gateId,
        status
      });

      return true;
    } catch (error) {
      this.logger.error('Failed to publish gate update event:', error);
      return false;
    }
  }

  async publishExecutionCompleted(operationId, summary) {
    try {
      if (!redisConfig.publisher) {
        this.logger.debug('Redis publisher not available, skipping event');
        return false;
      }

      const event = {
        event_type: 'control_execution_completed',
        operation_id: operationId,
        zone_id: summary.zoneId,
        week_start: summary.weekStart,
        status: 'completed',
        summary: {
          total_gates: summary.totalGates,
          successful_gates: summary.successfulGates,
          failed_gates: summary.failedGates,
          total_flow_rate_m3: summary.totalFlowRate,
          expected_delivery_m3: summary.expectedDelivery,
          execution_time_ms: summary.executionTimeMs
        },
        timestamp: new Date().toISOString()
      };

      await redisConfig.publisher.publish(
        'water:controls:status',
        JSON.stringify(event)
      );

      // Also publish to batch channel if part of batch operation
      if (summary.batchId) {
        await redisConfig.publisher.publish(
          'water:controls:batch',
          JSON.stringify({
            ...event,
            batch_id: summary.batchId
          })
        );
      }

      this.logger.info('Published execution completed event', {
        operation_id: operationId,
        zone_id: summary.zoneId,
        successful: summary.successfulGates,
        failed: summary.failedGates
      });

      return true;
    } catch (error) {
      this.logger.error('Failed to publish execution completed event:', error);
      return false;
    }
  }

  async publishMonitoringUpdate(zoneId, weekStart, metrics) {
    try {
      if (!redisConfig.publisher) {
        this.logger.debug('Redis publisher not available, skipping event');
        return false;
      }

      const event = {
        event_type: 'control_monitoring_update',
        zone_id: zoneId,
        week_start: weekStart,
        metrics: {
          scheduled_m3: metrics.scheduledM3,
          delivered_m3: metrics.deliveredM3,
          efficiency_pct: metrics.efficiencyPct,
          active_gates: metrics.activeGates,
          flow_rate_m3_per_hour: metrics.flowRateM3PerHour
        },
        timestamp: new Date().toISOString()
      };

      await redisConfig.publisher.publish(
        'water:controls:monitoring',
        JSON.stringify(event)
      );

      this.logger.debug('Published monitoring update', {
        zone_id: zoneId,
        efficiency: metrics.efficiencyPct
      });

      return true;
    } catch (error) {
      this.logger.error('Failed to publish monitoring update:', error);
      return false;
    }
  }

  async publishControlError(operationId, error) {
    try {
      if (!redisConfig.publisher) {
        this.logger.debug('Redis publisher not available, skipping event');
        return false;
      }

      const event = {
        event_type: 'control_error',
        operation_id: operationId,
        error: {
          code: error.code || 'UNKNOWN_ERROR',
          message: error.message,
          zone_id: error.zoneId,
          gate_id: error.gateId,
          severity: error.severity || 'error'
        },
        timestamp: new Date().toISOString()
      };

      await redisConfig.publisher.publish(
        'water:controls:errors',
        JSON.stringify(event)
      );

      this.logger.error('Published control error event', {
        operation_id: operationId,
        error_code: event.error.code
      });

      return true;
    } catch (publishError) {
      this.logger.error('Failed to publish error event:', publishError);
      return false;
    }
  }

  getEventStats() {
    return {
      publisher_ready: redisConfig.publisher?.isReady || false,
      redis_connected: redisConfig.isConnected
    };
  }
}

module.exports = new ControlFeedbackPublisher();