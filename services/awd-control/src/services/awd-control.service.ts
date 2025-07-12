import { getRedisClient } from '../config/redis';
import { getPostgresPool } from '../config/database';
import { logger } from '../utils/logger';
import { RedisKeys } from '../config/redis';
import { sensorManagementService } from './sensor-management.service';
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

export class AWDControlService {
  private redis = getRedisClient();
  private postgresPool = getPostgresPool();
  private readonly CRITICAL_MOISTURE_THRESHOLD = 20; // Below 20% is critical
  private readonly RAINFALL_THRESHOLD = 5; // 5mm rainfall affects irrigation

  /**
   * Initialize AWD control for a field
   */
  async initializeFieldControl(
    fieldId: string,
    plantingMethod: PlantingMethod,
    startDate: Date
  ): Promise<AWDFieldConfig> {
    try {
      const schedule = this.getScheduleTemplate(plantingMethod);
      const currentWeek = this.calculateCurrentWeek(startDate);
      const currentPhase = this.getCurrentPhase(schedule, currentWeek);
      
      const config: AWDFieldConfig = {
        fieldId,
        plantingMethod,
        startDate,
        currentWeek,
        currentPhase: currentPhase.phase,
        nextPhaseDate: this.calculateNextPhaseDate(startDate, schedule, currentWeek),
        isActive: true,
        hasRainfallData: false,
        targetWaterLevel: currentPhase.targetWaterLevel
      };

      // Store in Redis
      const configKey = RedisKeys.fieldConfig(fieldId);
      await this.redis.hset(configKey, {
        ...config,
        startDate: startDate.toISOString(),
        nextPhaseDate: config.nextPhaseDate.toISOString()
      });

      // Store in PostgreSQL
      await this.postgresPool.query(`
        INSERT INTO awd_configurations (
          field_id,
          planting_method,
          start_date,
          current_week,
          current_phase,
          target_water_level,
          active
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (field_id) 
        DO UPDATE SET
          planting_method = $2,
          start_date = $3,
          current_week = $4,
          current_phase = $5,
          target_water_level = $6,
          active = $7,
          updated_at = CURRENT_TIMESTAMP
      `, [
        fieldId,
        plantingMethod,
        startDate,
        currentWeek,
        currentPhase.phase,
        currentPhase.targetWaterLevel,
        true
      ]);

      logger.info({
        fieldId,
        plantingMethod,
        startDate,
        currentWeek,
        currentPhase: currentPhase.phase
      }, 'AWD control initialized for field');

      return config;
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to initialize AWD control');
      throw error;
    }
  }

  /**
   * Make irrigation control decision for a field
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

      // Make decision based on current phase
      const decision = await this.evaluatePhaseRequirements(
        config,
        waterLevel?.waterLevelCm || 0,
        moistureReading?.moisturePercent,
        rainfall,
        irrigationCheck
      );

      // Log decision
      logger.info({
        fieldId,
        decision: decision.action,
        reason: decision.reason,
        currentPhase: config.currentPhase,
        waterLevel: waterLevel?.waterLevelCm,
        moisture: moistureReading?.moisturePercent
      }, 'AWD control decision made');

      // Publish decision event
      await publishMessage(
        KafkaTopics.AWD_CONTROL_COMMANDS,
        {
          fieldId,
          decision,
          timestamp: new Date().toISOString()
        },
        fieldId
      );

      return decision;
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to make control decision');
      throw error;
    }
  }

  /**
   * Evaluate requirements based on current phase
   */
  private async evaluatePhaseRequirements(
    config: AWDFieldConfig,
    currentWaterLevel: number,
    moisturePercent: number | undefined,
    rainfall: RainfallData | null,
    sensorCheck: any
  ): Promise<AWDControlDecision> {
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
          estimatedDuration: 48, // 2 days
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

  /**
   * Evaluate wetting phase requirements
   */
  private evaluateWettingPhase(
    config: AWDFieldConfig,
    currentWaterLevel: number,
    rainfall: RainfallData | null,
    notifications: AWDNotification[]
  ): AWDControlDecision {
    // Check if we need fertilizer notification
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
      const estimatedWaterLevel = currentWaterLevel + (rainfall.amount / 10); // Convert mm to cm
      
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
        estimatedDuration: this.estimateIrrigationDuration(
          currentWaterLevel,
          config.targetWaterLevel
        ),
        notifications
      };
    }
  }

  /**
   * Evaluate drying phase requirements
   */
  private evaluateDryingPhase(
    config: AWDFieldConfig,
    _currentWaterLevel: number,
    moisturePercent: number | undefined,
    sensorCheck: any,
    notifications: AWDNotification[]
  ): AWDControlDecision {
    // Check moisture sensor if available
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
        estimatedDuration: 120, // 2 hours emergency irrigation
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

  /**
   * Update field progress if week has changed
   */
  private async updateFieldProgress(config: AWDFieldConfig): Promise<void> {
    const currentWeek = this.calculateCurrentWeek(config.startDate);
    
    if (currentWeek !== config.currentWeek) {
      const schedule = this.getScheduleTemplate(config.plantingMethod);
      const newPhase = this.getCurrentPhase(schedule, currentWeek);
      
      config.currentWeek = currentWeek;
      config.currentPhase = newPhase.phase;
      config.targetWaterLevel = newPhase.targetWaterLevel;
      config.nextPhaseDate = this.calculateNextPhaseDate(config.startDate, schedule, currentWeek);

      // Update Redis
      const configKey = RedisKeys.fieldConfig(config.fieldId);
      await this.redis.hset(configKey, {
        currentWeek: currentWeek.toString(),
        currentPhase: newPhase.phase,
        targetWaterLevel: newPhase.targetWaterLevel.toString(),
        nextPhaseDate: config.nextPhaseDate.toISOString()
      });

      // Update database
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

  /**
   * Get rainfall data for a field
   */
  private async getRainfallData(fieldId: string): Promise<RainfallData | null> {
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

  /**
   * Calculate current week based on start date
   */
  private calculateCurrentWeek(startDate: Date): number {
    const now = new Date();
    const diffTime = Math.abs(now.getTime() - startDate.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return Math.floor(diffDays / 7);
  }

  /**
   * Get current phase based on week
   */
  private getCurrentPhase(schedule: AWDSchedule, currentWeek: number): any {
    // Find the phase that covers the current week
    for (let i = schedule.phases.length - 1; i >= 0; i--) {
      if (currentWeek >= schedule.phases[i].week) {
        return schedule.phases[i];
      }
    }
    return schedule.phases[0];
  }

  /**
   * Calculate next phase date
   */
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

  /**
   * Get schedule template based on planting method
   */
  private getScheduleTemplate(plantingMethod: PlantingMethod): AWDSchedule {
    return plantingMethod === 'transplanted' 
      ? TRANSPLANTED_SCHEDULE 
      : DIRECT_SEEDED_SCHEDULE;
  }

  /**
   * Estimate irrigation duration to reach target level
   */
  private estimateIrrigationDuration(currentLevel: number, targetLevel: number): number {
    // Estimate based on typical flow rates
    // Assuming 1cm per hour average flow rate
    const depthNeeded = targetLevel - currentLevel;
    return Math.max(60, depthNeeded * 60); // Minutes, minimum 1 hour
  }

  /**
   * Get planting method from GIS/SHAPE data
   */
  async getPlantingMethodFromGIS(fieldId: string): Promise<PlantingMethod> {
    try {
      // Query GIS data for planting method
      const result = await this.postgresPool.query(`
        SELECT planting_method
        FROM gis.field_attributes
        WHERE field_id = $1
      `, [fieldId]);

      if (result.rows.length > 0 && result.rows[0].planting_method) {
        return result.rows[0].planting_method === 'transplanted' 
          ? 'transplanted' 
          : 'direct-seeded';
      }

      // Default to direct-seeded as specified
      return 'direct-seeded';
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get planting method from GIS');
      return 'direct-seeded';
    }
  }
}

export const awdControlService = new AWDControlService();