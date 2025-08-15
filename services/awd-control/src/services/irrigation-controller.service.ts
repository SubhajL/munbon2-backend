import { getPostgresPool, getTimescalePool } from '../config/database';
import { getRedisClient } from '../config/redis';
import { logger } from '../utils/logger';
import { publishMessage, KafkaTopics } from '../config/kafka';
import { sensorManagementService } from './sensor-management.service';
import { v4 as uuidv4 } from 'uuid';

export interface IrrigationConfig {
  fieldId: string;
  targetLevelCm: number;
  toleranceCm: number;
  maxDurationMinutes: number;
  sensorCheckIntervalSeconds: number;
  minFlowRateCmPerMin: number;
  emergencyStopLevel: number;
}

export interface IrrigationStatus {
  scheduleId: string;
  fieldId: string;
  status: 'preparing' | 'active' | 'completed' | 'failed' | 'cancelled';
  startTime: Date;
  currentLevelCm: number;
  targetLevelCm: number;
  flowRateCmPerMin: number;
  estimatedCompletionTime?: Date;
  anomaliesDetected: number;
}

export interface AnomalyDetection {
  type: 'low_flow' | 'no_rise' | 'rapid_drop' | 'sensor_failure' | 'overflow_risk';
  severity: 'warning' | 'critical';
  description: string;
  metrics: any;
}

export class IrrigationControllerService {
  private postgresPool = getPostgresPool();
  private timescalePool = getTimescalePool();
  private redis = getRedisClient();
  
  // Configuration defaults
  private readonly DEFAULT_TOLERANCE_CM = 1.0;
  private readonly DEFAULT_CHECK_INTERVAL_SEC = 300; // 5 minutes
  private readonly DEFAULT_MAX_DURATION_MIN = 1440; // 24 hours
  private readonly MIN_FLOW_RATE_CM_PER_MIN = 0.05; // 3cm/hour minimum
  private readonly NO_RISE_THRESHOLD_CHECKS = 3; // No rise after 3 checks = problem
  private readonly RAPID_DROP_THRESHOLD_CM = 2; // 2cm drop = leak
  
  // Active irrigation tracking
  private activeIrrigations = new Map<string, NodeJS.Timeout>();

  /**
   * Start water level-based irrigation control
   */
  async startIrrigation(config: IrrigationConfig): Promise<IrrigationStatus> {
    const scheduleId = uuidv4();
    const startTime = new Date();
    
    try {
      // Get initial water level
      const initialLevel = await this.getCurrentWaterLevel(config.fieldId);
      if (!initialLevel) {
        throw new Error('Cannot read initial water level');
      }

      // Check if already irrigating
      const existingIrrigation = await this.getActiveIrrigation(config.fieldId);
      if (existingIrrigation) {
        throw new Error(`Field ${config.fieldId} already has active irrigation`);
      }

      // Create irrigation schedule record
      await this.createIrrigationSchedule({
        scheduleId,
        fieldId: config.fieldId,
        targetLevel: config.targetLevelCm,
        initialLevel: initialLevel.waterLevelCm,
        startTime
      });

      // Open irrigation gates
      await this.controlGates(config.fieldId, 'open');

      // Start monitoring
      const monitorInterval = this.startMonitoring(scheduleId, config);
      this.activeIrrigations.set(scheduleId, monitorInterval);

      // Store status in Redis
      const status: IrrigationStatus = {
        scheduleId,
        fieldId: config.fieldId,
        status: 'active',
        startTime,
        currentLevelCm: initialLevel.waterLevelCm,
        targetLevelCm: config.targetLevelCm,
        flowRateCmPerMin: 0,
        anomaliesDetected: 0
      };

      await this.updateIrrigationStatus(status);

      logger.info({
        scheduleId,
        fieldId: config.fieldId,
        initialLevel: initialLevel.waterLevelCm,
        targetLevel: config.targetLevelCm
      }, 'Started water level-based irrigation');

      return status;
    } catch (error) {
      logger.error({ error, config }, 'Failed to start irrigation');
      throw error;
    }
  }

  /**
   * Monitor irrigation progress with real sensor feedback
   */
  private startMonitoring(scheduleId: string, config: IrrigationConfig): NodeJS.Timeout {
    let previousLevel = config.targetLevelCm;
    let previousTime = Date.now();
    let noRiseCount = 0;
    let totalVolume = 0;
    const levelHistory: Array<{ time: Date; level: number }> = [];

    const monitoringInterval = setInterval(async () => {
      try {
        // Get current water level
        const currentReading = await this.getCurrentWaterLevel(config.fieldId);
        if (!currentReading) {
          await this.handleSensorFailure(scheduleId, config.fieldId);
          return;
        }

        const currentLevel = currentReading.waterLevelCm;
        const currentTime = Date.now();
        const timeDeltaMin = (currentTime - previousTime) / 60000;

        // Calculate flow rate
        const levelChange = currentLevel - previousLevel;
        const flowRate = timeDeltaMin > 0 ? levelChange / timeDeltaMin : 0;

        // Store monitoring data
        await this.recordMonitoringData({
          scheduleId,
          fieldId: config.fieldId,
          waterLevel: currentLevel,
          flowRate,
          sensorId: currentReading.sensorId,
          timestamp: new Date()
        });

        // Update level history for anomaly detection
        levelHistory.push({ time: new Date(), level: currentLevel });
        if (levelHistory.length > 10) levelHistory.shift();

        // Check for anomalies
        const anomalies = await this.detectAnomalies({
          scheduleId,
          fieldId: config.fieldId,
          currentLevel,
          previousLevel,
          flowRate,
          levelHistory,
          noRiseCount,
          targetLevel: config.targetLevelCm
        });

        // Handle detected anomalies
        for (const anomaly of anomalies) {
          await this.handleAnomaly(scheduleId, config.fieldId, anomaly);
          
          if (anomaly.severity === 'critical') {
            await this.stopIrrigation(scheduleId, 'anomaly_detected');
            return;
          }
        }

        // Check if target reached
        if (currentLevel >= config.targetLevelCm - config.toleranceCm) {
          await this.completeIrrigation(scheduleId, {
            achievedLevel: currentLevel,
            totalDuration: (Date.now() - previousTime) / 60000,
            totalVolume,
            avgFlowRate: totalVolume / ((Date.now() - previousTime) / 60000)
          });
          return;
        }

        // Check for no rise condition
        if (flowRate < config.minFlowRateCmPerMin) {
          noRiseCount++;
          if (noRiseCount >= this.NO_RISE_THRESHOLD_CHECKS) {
            await this.handleAnomaly(scheduleId, config.fieldId, {
              type: 'no_rise',
              severity: 'critical',
              description: `No water level rise detected after ${noRiseCount} checks`,
              metrics: { flowRate, currentLevel }
            });
          }
        } else {
          noRiseCount = 0;
        }

        // Check timeout
        const elapsedMinutes = (Date.now() - new Date(await this.getStartTime(scheduleId)).getTime()) / 60000;
        if (elapsedMinutes > config.maxDurationMinutes) {
          await this.stopIrrigation(scheduleId, 'timeout');
          return;
        }

        // Update status
        await this.updateIrrigationStatus({
          scheduleId,
          fieldId: config.fieldId,
          status: 'active',
          startTime: new Date(await this.getStartTime(scheduleId)),
          currentLevelCm: currentLevel,
          targetLevelCm: config.targetLevelCm,
          flowRateCmPerMin: flowRate,
          estimatedCompletionTime: this.estimateCompletionTime(
            currentLevel,
            config.targetLevelCm,
            flowRate
          ),
          anomaliesDetected: anomalies.length
        });

        // Calculate volume (simplified)
        totalVolume += levelChange * 10000; // cm to liters conversion for 1 hectare

        previousLevel = currentLevel;
        previousTime = currentTime;

      } catch (error) {
        logger.error({ error, scheduleId }, 'Error in irrigation monitoring');
        await this.handleMonitoringError(scheduleId, config.fieldId, error);
      }
    }, config.sensorCheckIntervalSeconds * 1000);

    return monitoringInterval;
  }

  /**
   * Detect anomalies during irrigation
   */
  private async detectAnomalies(params: {
    scheduleId: string;
    fieldId: string;
    currentLevel: number;
    previousLevel: number;
    flowRate: number;
    levelHistory: Array<{ time: Date; level: number }>;
    noRiseCount: number;
    targetLevel: number;
  }): Promise<AnomalyDetection[]> {
    const anomalies: AnomalyDetection[] = [];

    // Low flow detection
    if (params.flowRate < this.MIN_FLOW_RATE_CM_PER_MIN && params.flowRate >= 0) {
      anomalies.push({
        type: 'low_flow',
        severity: 'warning',
        description: `Flow rate (${params.flowRate.toFixed(3)} cm/min) below minimum`,
        metrics: {
          flowRate: params.flowRate,
          threshold: this.MIN_FLOW_RATE_CM_PER_MIN
        }
      });
    }

    // Rapid drop detection (possible leak)
    if (params.currentLevel < params.previousLevel - this.RAPID_DROP_THRESHOLD_CM) {
      anomalies.push({
        type: 'rapid_drop',
        severity: 'critical',
        description: `Water level dropped ${(params.previousLevel - params.currentLevel).toFixed(2)}cm - possible leak`,
        metrics: {
          previousLevel: params.previousLevel,
          currentLevel: params.currentLevel,
          drop: params.previousLevel - params.currentLevel
        }
      });
    }

    // No rise detection
    if (params.noRiseCount >= this.NO_RISE_THRESHOLD_CHECKS) {
      anomalies.push({
        type: 'no_rise',
        severity: 'critical',
        description: 'No water level rise detected - possible gate or pump failure',
        metrics: {
          checksWithoutRise: params.noRiseCount,
          currentLevel: params.currentLevel
        }
      });
    }

    // Overflow risk detection
    if (params.currentLevel > params.targetLevel + 5) {
      anomalies.push({
        type: 'overflow_risk',
        severity: 'critical',
        description: 'Water level exceeding target by more than 5cm',
        metrics: {
          currentLevel: params.currentLevel,
          targetLevel: params.targetLevel,
          excess: params.currentLevel - params.targetLevel
        }
      });
    }

    // Store anomalies in database
    for (const anomaly of anomalies) {
      await this.recordAnomaly(params.scheduleId, params.fieldId, anomaly);
    }

    return anomalies;
  }

  /**
   * Handle detected anomalies
   */
  private async handleAnomaly(
    scheduleId: string,
    fieldId: string,
    anomaly: AnomalyDetection
  ): Promise<void> {
    logger.warn({ scheduleId, fieldId, anomaly }, 'Anomaly detected during irrigation');

    // Send alert
    await publishMessage(KafkaTopics.ALERT_NOTIFICATIONS, {
      type: 'irrigation_anomaly',
      scheduleId,
      fieldId,
      anomaly,
      timestamp: new Date().toISOString()
    });

    // Take action based on anomaly type
    switch (anomaly.type) {
      case 'rapid_drop':
      case 'overflow_risk':
        // Critical - stop irrigation immediately
        await this.stopIrrigation(scheduleId, 'anomaly_critical');
        break;
        
      case 'low_flow':
        // Warning - notify but continue
        await this.adjustGateFlow(fieldId, 'increase');
        break;
        
      case 'no_rise':
        // Check gate status and try to recover
        await this.attemptRecovery(scheduleId, fieldId);
        break;
        
      case 'sensor_failure':
        // Switch to backup sensor or estimation
        await this.switchToBackupSensor(fieldId);
        break;
    }
  }

  /**
   * Complete irrigation successfully
   */
  private async completeIrrigation(
    scheduleId: string,
    results: {
      achievedLevel: number;
      totalDuration: number;
      totalVolume: number;
      avgFlowRate: number;
    }
  ): Promise<void> {
    try {
      // Stop monitoring
      const interval = this.activeIrrigations.get(scheduleId);
      if (interval) {
        clearInterval(interval);
        this.activeIrrigations.delete(scheduleId);
      }

      // Close gates
      const status = await this.getIrrigationStatus(scheduleId);
      if (status) {
        await this.controlGates(status.fieldId, 'close');
      }

      // Update final status
      await this.updateIrrigationSchedule(scheduleId, {
        status: 'completed',
        endTime: new Date(),
        finalLevel: results.achievedLevel,
        waterVolume: results.totalVolume,
        avgFlowRate: results.avgFlowRate
      });

      // Record performance metrics
      await this.recordPerformanceMetrics(scheduleId, results);

      // Learn from this irrigation
      await this.updateLearningModel(scheduleId);

      logger.info({
        scheduleId,
        results
      }, 'Irrigation completed successfully');

    } catch (error) {
      logger.error({ error, scheduleId }, 'Error completing irrigation');
      throw error;
    }
  }

  /**
   * Stop irrigation (emergency or timeout)
   */
  async stopIrrigation(scheduleId: string, reason: string): Promise<void> {
    try {
      // Stop monitoring
      const interval = this.activeIrrigations.get(scheduleId);
      if (interval) {
        clearInterval(interval);
        this.activeIrrigations.delete(scheduleId);
      }

      // Get current status
      const status = await this.getIrrigationStatus(scheduleId);
      if (!status) return;

      // Close gates immediately
      await this.controlGates(status.fieldId, 'close');

      // Update status
      await this.updateIrrigationSchedule(scheduleId, {
        status: reason === 'anomaly_critical' ? 'failed' : 'cancelled',
        endTime: new Date(),
        finalLevel: status.currentLevelCm
      });

      logger.info({
        scheduleId,
        fieldId: status.fieldId,
        reason
      }, 'Irrigation stopped');

    } catch (error) {
      logger.error({ error, scheduleId }, 'Error stopping irrigation');
      throw error;
    }
  }

  /**
   * Estimate completion time based on current flow rate
   */
  private estimateCompletionTime(
    currentLevel: number,
    targetLevel: number,
    flowRate: number
  ): Date | undefined {
    if (flowRate <= 0) return undefined;

    const remainingCm = targetLevel - currentLevel;
    const remainingMinutes = remainingCm / flowRate;
    
    const completionTime = new Date();
    completionTime.setMinutes(completionTime.getMinutes() + remainingMinutes);
    
    return completionTime;
  }

  /**
   * Get current water level from sensors
   */
  private async getCurrentWaterLevel(fieldId: string): Promise<any> {
    return await sensorManagementService.getCurrentWaterLevel(fieldId);
  }

  /**
   * Control irrigation gates
   */
  private async controlGates(fieldId: string, action: 'open' | 'close' | 'adjust'): Promise<void> {
    try {
      // Get gate configuration for field
      const gates = await this.getFieldGates(fieldId);
      
      for (const gate of gates) {
        await this.sendGateCommand(gate.gateId, action);
        
        // Log gate control
        await this.postgresPool.query(`
          INSERT INTO awd.gate_control_logs 
          (field_id, gate_id, action, requested_at, executed_at, success)
          VALUES ($1, $2, $3, NOW(), NOW(), true)
        `, [fieldId, gate.gateId, action]);
      }

      // Publish gate control event
      await publishMessage(KafkaTopics.GATE_CONTROL_COMMANDS, {
        fieldId,
        gates: gates.map(g => g.gateId),
        action,
        timestamp: new Date().toISOString()
      });

    } catch (error) {
      logger.error({ error, fieldId, action }, 'Failed to control gates');
      throw error;
    }
  }

  /**
   * Database operations
   */
  private async createIrrigationSchedule(params: any): Promise<void> {
    await this.postgresPool.query(`
      INSERT INTO awd.irrigation_schedules
      (id, field_id, scheduled_start, target_level_cm, initial_level_cm, status)
      VALUES ($1, $2, $3, $4, $5, 'active')
    `, [params.scheduleId, params.fieldId, params.startTime, params.targetLevel, params.initialLevel]);
  }

  private async updateIrrigationSchedule(scheduleId: string, updates: any): Promise<void> {
    const setClauses = [];
    const values = [scheduleId];
    let paramCount = 1;

    if (updates.status) {
      setClauses.push(`status = $${++paramCount}`);
      values.push(updates.status);
    }
    if (updates.endTime) {
      setClauses.push(`actual_end = $${++paramCount}`);
      values.push(updates.endTime);
    }
    if (updates.finalLevel !== undefined) {
      setClauses.push(`final_level_cm = $${++paramCount}`);
      values.push(updates.finalLevel);
    }
    if (updates.waterVolume !== undefined) {
      setClauses.push(`water_volume_liters = $${++paramCount}`);
      values.push(updates.waterVolume);
    }
    if (updates.avgFlowRate !== undefined) {
      setClauses.push(`avg_flow_rate_cm_per_min = $${++paramCount}`);
      values.push(updates.avgFlowRate);
    }

    await this.postgresPool.query(`
      UPDATE awd.irrigation_schedules
      SET ${setClauses.join(', ')}, updated_at = CURRENT_TIMESTAMP
      WHERE id = $1
    `, values);
  }

  private async recordMonitoringData(data: any): Promise<void> {
    await this.postgresPool.query(`
      INSERT INTO awd.irrigation_monitoring
      (schedule_id, field_id, timestamp, water_level_cm, flow_rate_cm_per_min, sensor_id)
      VALUES ($1, $2, $3, $4, $5, $6)
    `, [data.scheduleId, data.fieldId, data.timestamp, data.waterLevel, data.flowRate, data.sensorId]);
  }

  private async recordAnomaly(scheduleId: string, fieldId: string, anomaly: AnomalyDetection): Promise<void> {
    await this.postgresPool.query(`
      INSERT INTO awd.irrigation_anomalies
      (schedule_id, field_id, detected_at, anomaly_type, severity, description, metrics)
      VALUES ($1, $2, NOW(), $3, $4, $5, $6)
    `, [scheduleId, fieldId, anomaly.type, anomaly.severity, anomaly.description, JSON.stringify(anomaly.metrics)]);
  }

  private async recordPerformanceMetrics(scheduleId: string, results: any): Promise<void> {
    // Get full irrigation data
    const irrigationData = await this.postgresPool.query(`
      SELECT * FROM awd.irrigation_schedules WHERE id = $1
    `, [scheduleId]);

    const schedule = irrigationData.rows[0];

    // Calculate efficiency score
    const targetAchieved = Math.abs(results.achievedLevel - schedule.target_level_cm) < 1;
    const timeEfficiency = results.totalDuration < 360 ? 1 : 360 / results.totalDuration; // 6 hours baseline
    const efficiencyScore = (targetAchieved ? 0.7 : 0.3) + (timeEfficiency * 0.3);

    await this.postgresPool.query(`
      INSERT INTO awd.irrigation_performance
      (field_id, schedule_id, start_time, end_time, initial_level_cm, target_level_cm, 
       achieved_level_cm, total_duration_minutes, water_volume_liters, avg_flow_rate_cm_per_min,
       efficiency_score)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
    `, [
      schedule.field_id, scheduleId, schedule.scheduled_start, new Date(),
      schedule.initial_level_cm, schedule.target_level_cm, results.achievedLevel,
      results.totalDuration, results.totalVolume, results.avgFlowRate,
      efficiencyScore
    ]);
  }

  /**
   * Update machine learning model with new data
   */
  private async updateLearningModel(scheduleId: string): Promise<void> {
    // This would integrate with your ML pipeline
    // For now, we'll just log the intent
    logger.info({ scheduleId }, 'Updating ML model with irrigation results');
    
    // TODO: Implement actual ML model update
    // - Extract features from this irrigation
    // - Update model with new training data
    // - Retrain if necessary
  }

  /**
   * Helper methods
   */
  private async getIrrigationStatus(scheduleId: string): Promise<IrrigationStatus | null> {
    const key = `irrigation:status:${scheduleId}`;
    const data = await this.redis.get(key);
    return data ? JSON.parse(data) : null;
  }

  private async updateIrrigationStatus(status: IrrigationStatus): Promise<void> {
    const key = `irrigation:status:${status.scheduleId}`;
    await this.redis.setex(key, 86400, JSON.stringify(status)); // 24 hour TTL
    
    // Also update field status
    const fieldKey = `irrigation:field:${status.fieldId}`;
    await this.redis.setex(fieldKey, 86400, status.scheduleId);
  }

  private async getActiveIrrigation(fieldId: string): Promise<string | null> {
    const key = `irrigation:field:${fieldId}`;
    return await this.redis.get(key);
  }

  private async getStartTime(scheduleId: string): Promise<number> {
    const status = await this.getIrrigationStatus(scheduleId);
    return status ? new Date(status.startTime).getTime() : Date.now();
  }

  private async handleSensorFailure(scheduleId: string, fieldId: string): Promise<void> {
    await this.handleAnomaly(scheduleId, fieldId, {
      type: 'sensor_failure',
      severity: 'critical',
      description: 'Cannot read water level sensor',
      metrics: { lastReadTime: new Date() }
    });
  }

  private async handleMonitoringError(scheduleId: string, fieldId: string, error: any): Promise<void> {
    logger.error({ error, scheduleId, fieldId }, 'Monitoring error occurred');
    // Decide whether to continue or stop based on error type
  }

  private async attemptRecovery(scheduleId: string, fieldId: string): Promise<void> {
    // Try to recover from no-rise condition
    // 1. Check gate status
    // 2. Try cycling gates
    // 3. Check for concurrent irrigations
    logger.info({ scheduleId, fieldId }, 'Attempting irrigation recovery');
  }

  private async switchToBackupSensor(fieldId: string): Promise<void> {
    // Switch to backup sensor or GIS data
    logger.info({ fieldId }, 'Switching to backup water level source');
  }

  private async adjustGateFlow(fieldId: string, direction: 'increase' | 'decrease'): Promise<void> {
    // Adjust gate opening percentage
    logger.info({ fieldId, direction }, 'Adjusting gate flow rate');
  }

  private async getFieldGates(fieldId: string): Promise<Array<{ gateId: string }>> {
    // Get gate configuration for field
    // This would come from field configuration
    return [{ gateId: `GATE_${fieldId}_1` }]; // Placeholder
  }

  private async sendGateCommand(gateId: string, action: string): Promise<void> {
    // Send actual command to SCADA system
    logger.info({ gateId, action }, 'Sending gate control command');
    // TODO: Implement SCADA integration
  }

  /**
   * Get irrigation recommendations based on historical performance
   */
  async getIrrigationRecommendation(fieldId: string, targetLevel: number): Promise<{
    estimatedDuration: number;
    recommendedStartTime: Date;
    expectedFlowRate: number;
    confidence: number;
  }> {
    try {
      // Get historical performance data
      const history = await this.postgresPool.query(`
        SELECT 
          AVG(total_duration_minutes) as avg_duration,
          AVG(avg_flow_rate_cm_per_min) as avg_flow_rate,
          COUNT(*) as sample_size,
          STDDEV(total_duration_minutes) as duration_stddev
        FROM awd.irrigation_performance
        WHERE field_id = $1
          AND target_level_cm = $2
          AND efficiency_score > 0.7
          AND start_time > NOW() - INTERVAL '30 days'
      `, [fieldId, targetLevel]);

      if (history.rows.length === 0 || history.rows[0].sample_size < 3) {
        // Not enough data, use defaults
        return {
          estimatedDuration: (targetLevel - 0) * 60, // Basic calculation
          recommendedStartTime: new Date(),
          expectedFlowRate: 0.1, // 6cm/hour default
          confidence: 0.3
        };
      }

      const data = history.rows[0];
      const confidence = Math.min(0.9, 0.3 + (data.sample_size * 0.1));

      return {
        estimatedDuration: Math.round(data.avg_duration),
        recommendedStartTime: this.calculateOptimalStartTime(fieldId),
        expectedFlowRate: parseFloat(data.avg_flow_rate),
        confidence
      };

    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get irrigation recommendation');
      throw error;
    }
  }

  private calculateOptimalStartTime(fieldId: string): Date {
    // TODO: Consider factors like:
    // - Other fields' schedules
    // - Peak/off-peak hours
    // - Weather forecast
    // - Power availability
    
    const startTime = new Date();
    startTime.setHours(6, 0, 0, 0); // Default: 6 AM
    return startTime;
  }
}

export const irrigationControllerService = new IrrigationControllerService();