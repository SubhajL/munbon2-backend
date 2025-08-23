import { getPostgresPool, getTimescalePool } from '../config/database';
import { getRedisClient } from '../config/redis';
import { logger } from '../utils/logger';
import { publishMessage, KafkaTopics } from '../config/kafka';
import { sensorManagementService } from './sensor-management.service';
import { scadaGateControlService } from './scada-gate-control.service';
import { v4 as uuidv4 } from 'uuid';

export interface IrrigationConfig {
  fieldId: string;
  targetLevelCm: number;
  toleranceCm: number;
  maxDurationMinutes: number;
  sensorCheckIntervalSeconds: number;
  minFlowRateCmPerMin: number;
  emergencyStopLevel: number;
  targetFlowRate?: number; // m³/s
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

export class IrrigationControllerV2Service {
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
   * Start water level-based irrigation control (without pumps)
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
        startTime,
        targetFlowRate: config.targetFlowRate
      });

      // Calculate required flow rate based on field size and target
      const requiredFlowRate = await this.calculateRequiredFlowRate(
        config.fieldId,
        initialLevel.waterLevelCm,
        config.targetLevelCm
      );

      // Open irrigation gates through SCADA
      await scadaGateControlService.openGateForFlow(
        config.fieldId,
        config.targetFlowRate || requiredFlowRate
      );

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
        targetLevel: config.targetLevelCm,
        requiredFlowRate
      }, 'Started water level-based irrigation (gate control only)');

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

        // Get canal water levels from Flow Monitoring Service
        const canalLevels = await scadaGateControlService.getCanalWaterLevels();
        await this.storeCanalLevels(scheduleId, canalLevels);

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
   * Calculate required flow rate based on field parameters
   */
  private async calculateRequiredFlowRate(
    fieldId: string,
    currentLevel: number,
    targetLevel: number
  ): Promise<number> {
    try {
      // Get field area
      const fieldResult = await this.postgresPool.query(`
        SELECT area_hectares, soil_type
        FROM awd.awd_fields
        WHERE id = $1
      `, [fieldId]);

      if (fieldResult.rows.length === 0) {
        throw new Error('Field not found');
      }

      const { area_hectares, soil_type } = fieldResult.rows[0];
      
      // Calculate water volume needed (m³)
      const depthNeeded = (targetLevel - currentLevel) / 100; // cm to m
      const volumeNeeded = area_hectares * 10000 * depthNeeded; // m³

      // Estimate flow rate based on soil percolation
      const percolationRate = this.getPercolationRate(soil_type); // m³/hr/ha
      const totalPercolation = percolationRate * area_hectares;

      // Target to complete in 6 hours
      const targetDurationHours = 6;
      const baseFlowRate = volumeNeeded / targetDurationHours;
      
      // Add percolation compensation
      const requiredFlowRate = baseFlowRate + totalPercolation;

      // Convert to m³/s
      return requiredFlowRate / 3600;

    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to calculate flow rate');
      // Default fallback
      return 5.0; // 5 m³/s default
    }
  }

  /**
   * Get soil percolation rate
   */
  private getPercolationRate(soilType: string): number {
    const rates: Record<string, number> = {
      'clay': 1.0,      // m³/hr/ha
      'loam': 2.0,
      'sandy_loam': 3.0,
      'sand': 4.0
    };
    
    return rates[soilType] || 2.0; // Default to loam
  }

  /**
   * Store canal water levels
   */
  private async storeCanalLevels(scheduleId: string, levels: any): Promise<void> {
    try {
      await this.postgresPool.query(`
        INSERT INTO awd.canal_water_levels
        (schedule_id, timestamp, levels_data)
        VALUES ($1, NOW(), $2)
      `, [scheduleId, JSON.stringify(levels)]);
    } catch (error) {
      logger.error({ error, scheduleId }, 'Failed to store canal levels');
    }
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
        description: 'No water level rise detected - possible gate or canal issue',
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
        logger.info({ fieldId }, 'Low flow detected - may need gate adjustment');
        break;
        
      case 'no_rise':
        // Check canal status
        const canalStatus = await scadaGateControlService.getCanalWaterLevels();
        logger.info({ fieldId, canalStatus }, 'Checking canal status due to no rise');
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
        await scadaGateControlService.closeGate(status.fieldId);
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
      await scadaGateControlService.closeGate(status.fieldId);

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
   * Database operations
   */
  private async createIrrigationSchedule(params: any): Promise<void> {
    await this.postgresPool.query(`
      INSERT INTO awd.irrigation_schedules
      (id, field_id, scheduled_start, target_level_cm, initial_level_cm, 
       target_flow_rate, status)
      VALUES ($1, $2, $3, $4, $5, $6, 'active')
    `, [
      params.scheduleId, 
      params.fieldId, 
      params.startTime, 
      params.targetLevel, 
      params.initialLevel,
      params.targetFlowRate
    ]);
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
    logger.info({ scheduleId }, 'Updating ML model with irrigation results');
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

  private async switchToBackupSensor(fieldId: string): Promise<void> {
    // Switch to backup sensor or GIS data
    logger.info({ fieldId }, 'Switching to backup water level source');
  }
}

export const irrigationControllerV2Service = new IrrigationControllerV2Service();