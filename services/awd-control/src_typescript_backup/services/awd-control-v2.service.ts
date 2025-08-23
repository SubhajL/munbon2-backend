import { getRedisClient } from '../config/redis';
import { getPostgresPool } from '../config/database';
import { logger } from '../utils/logger';
import { RedisKeys } from '../config/redis';
import { sensorManagementService } from './sensor-management.service';
import { irrigationControllerService } from './irrigation-controller.service';
import { irrigationLearningService } from './irrigation-learning.service';
import { publishMessage, KafkaTopics } from '../config/kafka';
import { weatherIntegration } from '../integrations/weather.integration';
import {
  PlantingMethod,
  AWDPhase,
  AWDSchedule,
  AWDFieldConfig,
  AWDControlDecision,
  AWDNotification,
  RainfallData,
  TRANSPLANTED_SCHEDULE,
  DIRECT_SEEDED_SCHEDULE
} from '../types/awd-control.types';

/**
 * Enhanced AWD Control Service with Water Level-Based Control
 * This version uses real sensor feedback instead of time-based estimates
 */
export class AWDControlServiceV2 {
  private redis = getRedisClient();
  private postgresPool = getPostgresPool();
  private readonly CRITICAL_MOISTURE_THRESHOLD = 20; // Below 20% is critical
  private readonly RAINFALL_THRESHOLD = 5; // 5mm rainfall affects irrigation

  /**
   * Make irrigation control decision with enhanced logic
   */
  async makeControlDecision(fieldId: string): Promise<AWDControlDecision> {
    try {
      // Get field configuration
      const config = await this.getFieldConfig(fieldId);
      if (!config || !config.isActive) {
        return {
          fieldId,
          action: 'maintain',
          reason: 'Field AWD control not active'
        };
      }

      // Update current week if needed
      await this.updateFieldProgress(config);

      // Get current sensor readings
      const [waterLevel, moistureReading, irrigationCheck] = await Promise.all([
        sensorManagementService.getCurrentWaterLevel(fieldId),
        sensorManagementService.getCurrentMoistureLevel(fieldId),
        sensorManagementService.checkIrrigationNeed(fieldId)
      ]);

      // Get rainfall data
      const rainfall = await this.getRainfallData(fieldId);

      // Check if irrigation is already active
      const activeIrrigation = await this.getActiveIrrigation(fieldId);
      if (activeIrrigation) {
        return {
          fieldId,
          action: 'maintain',
          reason: `Irrigation already active (${activeIrrigation.status})`,
          metadata: activeIrrigation
        };
      }

      // Make decision based on current phase
      const decision = await this.evaluatePhaseRequirements(
        config,
        waterLevel?.waterLevelCm || 0,
        moistureReading?.moisturePercent,
        rainfall,
        irrigationCheck
      );

      // If decision is to irrigate, get enhanced parameters
      if (decision.action === 'start_irrigation') {
        const enhancedDecision = await this.enhanceIrrigationDecision(
          fieldId,
          decision,
          waterLevel?.waterLevelCm || 0
        );
        return enhancedDecision;
      }

      // Log decision
      logger.info({
        fieldId,
        decision: decision.action,
        reason: decision.reason,
        currentPhase: config.currentPhase,
        waterLevel: waterLevel?.waterLevelCm,
        moisture: moistureReading?.moisturePercent
      }, 'AWD control decision made');

      return decision;
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to make control decision');
      throw error;
    }
  }

  /**
   * Execute irrigation with water level-based control
   */
  async executeIrrigation(fieldId: string, decision: AWDControlDecision): Promise<any> {
    try {
      if (decision.action !== 'start_irrigation') {
        return { success: false, reason: 'Not an irrigation decision' };
      }

      // Get optimal parameters from learning service
      const optimalParams = await irrigationLearningService.getOptimalParameters(fieldId);

      // Get current water level
      const currentLevel = await sensorManagementService.getCurrentWaterLevel(fieldId);
      if (!currentLevel) {
        throw new Error('Cannot read current water level');
      }

      // Start water level-based irrigation
      const irrigationStatus = await irrigationControllerService.startIrrigation({
        fieldId,
        targetLevelCm: decision.targetWaterLevel || 10,
        toleranceCm: optimalParams.toleranceCm,
        maxDurationMinutes: optimalParams.maxDurationMinutes,
        sensorCheckIntervalSeconds: optimalParams.sensorCheckInterval,
        minFlowRateCmPerMin: optimalParams.minFlowRateThreshold,
        emergencyStopLevel: 15 // Stop if water rises above 15cm
      });

      // Publish irrigation started event
      await publishMessage(
        KafkaTopics.AWD_IRRIGATION_EVENTS,
        {
          type: 'irrigation_started',
          fieldId,
          scheduleId: irrigationStatus.scheduleId,
          targetLevel: decision.targetWaterLevel,
          estimatedDuration: decision.estimatedDuration,
          method: 'water_level_based',
          timestamp: new Date().toISOString()
        },
        fieldId
      );

      return {
        success: true,
        scheduleId: irrigationStatus.scheduleId,
        status: irrigationStatus,
        method: 'water_level_based'
      };

    } catch (error) {
      logger.error({ error, fieldId, decision }, 'Failed to execute irrigation');
      throw error;
    }
  }

  /**
   * Get irrigation status and recommendations
   */
  async getIrrigationStatus(fieldId: string): Promise<any> {
    try {
      // Check for active irrigation
      const activeScheduleId = await this.getActiveIrrigationId(fieldId);
      
      if (activeScheduleId) {
        // Get real-time status
        const status = await this.redis.get(`irrigation:status:${activeScheduleId}`);
        if (status) {
          return {
            active: true,
            ...JSON.parse(status)
          };
        }
      }

      // Get field status
      const [waterLevel, config, patterns] = await Promise.all([
        sensorManagementService.getCurrentWaterLevel(fieldId),
        this.getFieldConfig(fieldId),
        irrigationLearningService.analyzeFieldPatterns(fieldId)
      ]);

      // Get recommendations
      const recommendation = await this.getIrrigationRecommendation(
        fieldId,
        config,
        waterLevel?.waterLevelCm || 0
      );

      return {
        active: false,
        fieldId,
        currentWaterLevel: waterLevel?.waterLevelCm,
        currentPhase: config?.currentPhase,
        patterns,
        recommendation
      };

    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get irrigation status');
      throw error;
    }
  }

  /**
   * Stop active irrigation
   */
  async stopIrrigation(fieldId: string, reason: string): Promise<any> {
    try {
      const activeScheduleId = await this.getActiveIrrigationId(fieldId);
      
      if (!activeScheduleId) {
        return { success: false, reason: 'No active irrigation found' };
      }

      // Stop irrigation
      await irrigationControllerService.stopIrrigation(activeScheduleId, reason);

      // Publish event
      await publishMessage(
        KafkaTopics.AWD_IRRIGATION_EVENTS,
        {
          type: 'irrigation_stopped',
          fieldId,
          scheduleId: activeScheduleId,
          reason,
          timestamp: new Date().toISOString()
        },
        fieldId
      );

      return {
        success: true,
        scheduleId: activeScheduleId,
        reason
      };

    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to stop irrigation');
      throw error;
    }
  }

  /**
   * Enhanced decision making with learning insights
   */
  private async enhanceIrrigationDecision(
    fieldId: string,
    baseDecision: AWDControlDecision,
    currentLevel: number
  ): Promise<AWDControlDecision> {
    try {
      // Get prediction from learning service
      const prediction = await irrigationLearningService.predictIrrigationPerformance(
        fieldId,
        {
          initialLevel: currentLevel,
          targetLevel: baseDecision.targetWaterLevel || 10,
          soilType: await this.getFieldSoilType(fieldId),
          temperature: await this.getCurrentTemperature(fieldId),
          humidity: await this.getCurrentHumidity(fieldId),
          lastIrrigationDays: await this.getDaysSinceLastIrrigation(fieldId),
          concurrentIrrigations: await this.getConcurrentIrrigations(),
          season: this.getCurrentSeason()
        }
      );

      // Get recommendations
      const recommendation = await irrigationLearningService.getIrrigationRecommendation(
        fieldId,
        baseDecision.targetWaterLevel || 10
      );

      // Enhance decision with predictions
      return {
        ...baseDecision,
        estimatedDuration: prediction.predictions.estimatedDuration,
        metadata: {
          method: 'water_level_based',
          prediction: {
            duration: prediction.predictions.estimatedDuration,
            flowRate: prediction.predictions.expectedFlowRate,
            waterVolume: prediction.predictions.waterVolume,
            confidence: prediction.predictions.confidenceLevel,
            basedOnSamples: prediction.basedOnSamples
          },
          recommendation: {
            startTime: recommendation.recommendedStartTime,
            confidence: recommendation.confidence
          }
        }
      };

    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to enhance irrigation decision');
      return baseDecision;
    }
  }

  /**
   * Get irrigation recommendation
   */
  private async getIrrigationRecommendation(
    fieldId: string,
    config: AWDFieldConfig | null,
    currentLevel: number
  ): Promise<any> {
    if (!config) return null;

    const schedule = this.getScheduleTemplate(config.plantingMethod);
    const currentPhaseInfo = this.getCurrentPhase(schedule, config.currentWeek);

    // Check if irrigation is needed
    const needsIrrigation = currentLevel < currentPhaseInfo.targetWaterLevel - 2;

    if (!needsIrrigation) {
      return {
        action: 'maintain',
        reason: 'Water level within acceptable range',
        nextCheck: new Date(Date.now() + 24 * 60 * 60 * 1000) // 24 hours
      };
    }

    // Get prediction
    const prediction = await irrigationLearningService.getIrrigationRecommendation(
      fieldId,
      currentPhaseInfo.targetWaterLevel
    );

    return {
      action: 'irrigate',
      targetLevel: currentPhaseInfo.targetWaterLevel,
      estimatedDuration: prediction.estimatedDuration,
      recommendedStartTime: prediction.recommendedStartTime,
      expectedFlowRate: prediction.expectedFlowRate,
      confidence: prediction.confidence,
      reason: `Water level (${currentLevel}cm) below target (${currentPhaseInfo.targetWaterLevel}cm)`
    };
  }

  /**
   * Helper methods
   */
  private async getActiveIrrigationId(fieldId: string): Promise<string | null> {
    const key = `irrigation:field:${fieldId}`;
    return await this.redis.get(key);
  }

  private async getActiveIrrigation(fieldId: string): Promise<any> {
    const scheduleId = await this.getActiveIrrigationId(fieldId);
    if (!scheduleId) return null;

    const statusKey = `irrigation:status:${scheduleId}`;
    const status = await this.redis.get(statusKey);
    return status ? JSON.parse(status) : null;
  }

  private async getFieldSoilType(fieldId: string): Promise<string> {
    const result = await this.postgresPool.query(
      'SELECT soil_type FROM awd.awd_fields WHERE id = $1',
      [fieldId]
    );
    return result.rows[0]?.soil_type || 'loam';
  }

  private async getCurrentTemperature(fieldId: string): Promise<number> {
    try {
      const weather = await weatherIntegration.getCurrentWeather(fieldId);
      return weather?.temperature || 28;
    } catch {
      return 28; // Default
    }
  }

  private async getCurrentHumidity(fieldId: string): Promise<number> {
    try {
      const weather = await weatherIntegration.getCurrentWeather(fieldId);
      return weather?.humidity || 70;
    } catch {
      return 70; // Default
    }
  }

  private async getDaysSinceLastIrrigation(fieldId: string): Promise<number> {
    const result = await this.postgresPool.query(`
      SELECT MAX(actual_end) as last_irrigation
      FROM awd.irrigation_schedules
      WHERE field_id = $1 AND status = 'completed'
    `, [fieldId]);

    if (result.rows[0]?.last_irrigation) {
      const daysSince = (Date.now() - new Date(result.rows[0].last_irrigation).getTime()) / (1000 * 60 * 60 * 24);
      return Math.round(daysSince);
    }
    return 7; // Default
  }

  private async getConcurrentIrrigations(): Promise<number> {
    const result = await this.postgresPool.query(`
      SELECT COUNT(*) as count
      FROM awd.irrigation_schedules
      WHERE status = 'active'
    `);
    return parseInt(result.rows[0]?.count || '0');
  }

  private getCurrentSeason(): string {
    const month = new Date().getMonth();
    if (month >= 10 || month <= 1) return 'dry';
    if (month >= 5 && month <= 9) return 'wet';
    return 'normal';
  }

  // ... (include all other methods from original AWDControlService that don't need changes)
  // Methods like getFieldConfig, updateFieldProgress, evaluatePhaseRequirements, etc.
  // remain the same as they handle the decision logic, not the execution

  /**
   * Get field configuration from Redis/DB
   */
  private async getFieldConfig(fieldId: string): Promise<AWDFieldConfig | null> {
    try {
      // Try Redis first
      const configKey = RedisKeys.fieldConfig(fieldId);
      const cached = await this.redis.hgetall(configKey);
      
      if (cached && Object.keys(cached).length > 0) {
        return {
          fieldId: cached.fieldId,
          plantingMethod: cached.plantingMethod as PlantingMethod,
          startDate: new Date(cached.startDate),
          currentWeek: parseInt(cached.currentWeek),
          currentPhase: cached.currentPhase as AWDPhase,
          nextPhaseDate: new Date(cached.nextPhaseDate),
          isActive: cached.isActive === 'true',
          hasRainfallData: cached.hasRainfallData === 'true',
          targetWaterLevel: parseInt(cached.targetWaterLevel)
        };
      }

      // Fallback to database
      const result = await this.postgresPool.query(`
        SELECT 
          field_id,
          planting_method,
          start_date,
          current_week,
          current_phase,
          target_water_level,
          active
        FROM awd_configurations
        WHERE field_id = $1
      `, [fieldId]);

      if (result.rows.length === 0) {
        return null;
      }

      const row = result.rows[0];
      const schedule = this.getScheduleTemplate(row.planting_method);
      const config: AWDFieldConfig = {
        fieldId: row.field_id,
        plantingMethod: row.planting_method,
        startDate: row.start_date,
        currentWeek: row.current_week,
        currentPhase: row.current_phase,
        nextPhaseDate: this.calculateNextPhaseDate(row.start_date, schedule, row.current_week),
        isActive: row.active,
        hasRainfallData: false,
        targetWaterLevel: row.target_water_level
      };

      // Cache it
      await this.redis.hset(configKey, {
        ...config,
        startDate: config.startDate.toISOString(),
        nextPhaseDate: config.nextPhaseDate.toISOString()
      });

      return config;
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get field config');
      return null;
    }
  }

  private getScheduleTemplate(plantingMethod: PlantingMethod): AWDSchedule {
    return plantingMethod === 'transplanted' 
      ? TRANSPLANTED_SCHEDULE 
      : DIRECT_SEEDED_SCHEDULE;
  }

  private calculateCurrentWeek(startDate: Date): number {
    const now = new Date();
    const diffTime = Math.abs(now.getTime() - startDate.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return Math.floor(diffDays / 7);
  }

  private getCurrentPhase(schedule: AWDSchedule, currentWeek: number): any {
    // Find the phase that covers the current week
    for (let i = schedule.phases.length - 1; i >= 0; i--) {
      if (currentWeek >= schedule.phases[i].week) {
        return schedule.phases[i];
      }
    }
    return schedule.phases[0];
  }

  private calculateNextPhaseDate(startDate: Date, schedule: AWDSchedule, currentWeek: number): Date {
    const currentPhaseIndex = schedule.phases.findIndex(phase => 
      currentWeek >= phase.week && 
      (schedule.phases[schedule.phases.indexOf(phase) + 1]?.week > currentWeek || 
       schedule.phases.indexOf(phase) === schedule.phases.length - 1)
    );

    if (currentPhaseIndex < schedule.phases.length - 1) {
      const nextPhase = schedule.phases[currentPhaseIndex + 1];
      const nextPhaseDate = new Date(startDate);
      nextPhaseDate.setDate(nextPhaseDate.getDate() + (nextPhase.week * 7));
      return nextPhaseDate;
    }

    // If last phase, return end of schedule
    const endDate = new Date(startDate);
    endDate.setDate(endDate.getDate() + (schedule.totalWeeks * 7));
    return endDate;
  }

  // Include evaluatePhaseRequirements and other evaluation methods from original service
  private async evaluatePhaseRequirements(
    config: AWDFieldConfig,
    currentWaterLevel: number,
    moisturePercent: number | undefined,
    rainfall: RainfallData | null,
    sensorCheck: any
  ): Promise<AWDControlDecision> {
    // Same implementation as original
    const notifications: AWDNotification[] = [];

    switch (config.currentPhase) {
      case 'wetting':
        return this.evaluateWettingPhase(
          config,
          currentWaterLevel,
          rainfall,
          notifications
        );

      case 'drying':
        return this.evaluateDryingPhase(
          config,
          currentWaterLevel,
          moisturePercent,
          sensorCheck,
          notifications
        );

      case 'preparation':
        return {
          fieldId: config.fieldId,
          action: 'start_irrigation',
          reason: 'Field preparation phase',
          targetWaterLevel: 10,
          estimatedDuration: 48, // Will be overridden by prediction
          notifications
        };

      case 'harvest':
        return {
          fieldId: config.fieldId,
          action: 'stop_irrigation',
          reason: 'Harvest preparation phase',
          notifications: [{
            type: 'phase_change',
            message: 'Field entering harvest preparation - stop all irrigation',
            priority: 'high'
          }]
        };

      default:
        return {
          fieldId: config.fieldId,
          action: 'maintain',
          reason: 'Unknown phase'
        };
    }
  }

  private async updateFieldProgress(config: AWDFieldConfig): Promise<void> {
    // Same implementation as original
    const currentWeek = this.calculateCurrentWeek(config.startDate);
    
    if (currentWeek !== config.currentWeek) {
      const schedule = this.getScheduleTemplate(config.plantingMethod);
      const newPhase = this.getCurrentPhase(schedule, currentWeek);
      
      config.currentWeek = currentWeek;
      config.currentPhase = newPhase.phase;
      config.targetWaterLevel = newPhase.targetWaterLevel;
      config.nextPhaseDate = this.calculateNextPhaseDate(config.startDate, schedule, currentWeek);

      // Update Redis and database
      const configKey = RedisKeys.fieldConfig(config.fieldId);
      await this.redis.hset(configKey, {
        currentWeek: currentWeek.toString(),
        currentPhase: newPhase.phase,
        targetWaterLevel: newPhase.targetWaterLevel.toString(),
        nextPhaseDate: config.nextPhaseDate.toISOString()
      });

      await this.postgresPool.query(`
        UPDATE awd_configurations
        SET 
          current_week = $2,
          current_phase = $3,
          target_water_level = $4,
          updated_at = CURRENT_TIMESTAMP
        WHERE field_id = $1
      `, [config.fieldId, currentWeek, newPhase.phase, newPhase.targetWaterLevel]);

      // Send phase change notification
      await publishMessage(
        KafkaTopics.ALERT_NOTIFICATIONS,
        {
          type: 'phase_change',
          fieldId: config.fieldId,
          message: `Field entering ${newPhase.description} (Week ${currentWeek})`,
          priority: 'medium',
          timestamp: new Date().toISOString()
        },
        config.fieldId
      );
    }
  }

  private async getRainfallData(fieldId: string): Promise<RainfallData | null> {
    // Same implementation as original
    try {
      const rainfall = await weatherIntegration.getCurrentRainfall(fieldId);
      if (rainfall) {
        // Store in Redis for quick access
        const rainfallKey = `awd:rainfall:${fieldId}`;
        await this.redis.setex(
          rainfallKey,
          300, // 5 minutes cache
          JSON.stringify(rainfall)
        );
      }
      return rainfall;
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get rainfall data');
      return null;
    }
  }

  private evaluateWettingPhase(
    config: AWDFieldConfig,
    currentWaterLevel: number,
    rainfall: RainfallData | null,
    notifications: AWDNotification[]
  ): AWDControlDecision {
    // Same implementation as original
    const schedule = this.getScheduleTemplate(config.plantingMethod);
    const currentPhaseInfo = this.getCurrentPhase(schedule, config.currentWeek);
    
    if (currentPhaseInfo.requiresFertilizer && config.currentWeek === currentPhaseInfo.week) {
      notifications.push({
        type: 'fertilizer',
        message: `Fertilizer application recommended for ${currentPhaseInfo.description}`,
        priority: 'high',
        scheduledFor: new Date()
      });
    }

    // Check rainfall impact
    if (rainfall && rainfall.amount > this.RAINFALL_THRESHOLD) {
      const estimatedWaterLevel = currentWaterLevel + (rainfall.amount / 10);
      
      if (estimatedWaterLevel >= config.targetWaterLevel) {
        return {
          fieldId: config.fieldId,
          action: 'stop_irrigation',
          reason: `Rainfall (${rainfall.amount}mm) sufficient for target level`,
          notifications
        };
      }
    }

    // Check current water level
    if (currentWaterLevel >= config.targetWaterLevel) {
      return {
        fieldId: config.fieldId,
        action: 'maintain',
        reason: `Target water level (${config.targetWaterLevel}cm) achieved`,
        notifications
      };
    } else {
      return {
        fieldId: config.fieldId,
        action: 'start_irrigation',
        reason: `Water level (${currentWaterLevel}cm) below target (${config.targetWaterLevel}cm)`,
        targetWaterLevel: config.targetWaterLevel,
        notifications
      };
    }
  }

  private evaluateDryingPhase(
    config: AWDFieldConfig,
    currentWaterLevel: number,
    moisturePercent: number | undefined,
    sensorCheck: any,
    notifications: AWDNotification[]
  ): AWDControlDecision {
    // Same implementation as original
    if (moisturePercent !== undefined && moisturePercent < this.CRITICAL_MOISTURE_THRESHOLD) {
      notifications.push({
        type: 'emergency',
        message: `Critical moisture level (${moisturePercent}%) - immediate irrigation recommended`,
        priority: 'high'
      });

      return {
        fieldId: config.fieldId,
        action: 'start_irrigation',
        reason: `Moisture critically low (${moisturePercent}%)`,
        targetWaterLevel: 10,
        notifications
      };
    }

    // Check if sensor-based irrigation is needed
    if (sensorCheck.needsIrrigation && sensorCheck.reason === 'moisture_threshold') {
      return {
        fieldId: config.fieldId,
        action: 'start_irrigation',
        reason: 'Moisture threshold reached',
        targetWaterLevel: 10,
        notifications
      };
    }

    // During drying phase, normally stop irrigation
    return {
      fieldId: config.fieldId,
      action: 'stop_irrigation',
      reason: `Drying phase - Week ${config.currentWeek}`,
      notifications
    };
  }
}

export const awdControlServiceV2 = new AWDControlServiceV2();