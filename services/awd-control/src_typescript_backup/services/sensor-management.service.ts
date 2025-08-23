import { sensorRepository } from '../repositories/sensor.repository';
import { getRedisClient } from '../config/redis';
import { logger } from '../utils/logger';
import { RedisKeys } from '../config/redis';
import {
  WaterLevelReading,
  MoistureReading,
  SensorStatus
} from '../types/sensor.types';

export class SensorManagementService {
  private redis = getRedisClient();
  private readonly CACHE_TTL = 300; // 5 minutes
  private readonly MOISTURE_THRESHOLD_DRY = 30; // 30% moisture = need irrigation
  private readonly DEFAULT_DRYING_DAYS = 7; // Default days for drying cycle

  /**
   * Get current water level for a field
   * Uses sensor data if available, falls back to GIS data
   */
  async getCurrentWaterLevel(fieldId: string): Promise<WaterLevelReading | null> {
    try {
      // Check cache first
      const cacheKey = RedisKeys.sensorReading(`water_${fieldId}`);
      const cached = await this.redis.get(cacheKey);
      
      if (cached) {
        return JSON.parse(cached);
      }

      // Get sensor configuration (for future use)
      await sensorRepository.getFieldSensorConfig(fieldId);
      
      // Get latest water level reading
      const waterLevel = await sensorRepository.getLatestWaterLevel(fieldId);
      
      if (waterLevel) {
        // Cache the reading
        await this.redis.setex(
          cacheKey,
          this.CACHE_TTL,
          JSON.stringify(waterLevel)
        );

        // Update sensor last reading if from sensor
        if (waterLevel.source === 'sensor') {
          await sensorRepository.updateSensorLastReading(
            waterLevel.sensorId,
            waterLevel.time
          );
        }

        logger.info({
          fieldId,
          waterLevel: waterLevel.waterLevelCm,
          source: waterLevel.source
        }, 'Water level reading retrieved');
      } else {
        logger.warn({ fieldId }, 'No water level data available');
      }

      return waterLevel;
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get current water level');
      throw error;
    }
  }

  /**
   * Get current moisture level for a field
   */
  async getCurrentMoistureLevel(fieldId: string): Promise<MoistureReading | null> {
    try {
      // Check cache first
      const cacheKey = RedisKeys.sensorReading(`moisture_${fieldId}`);
      const cached = await this.redis.get(cacheKey);
      
      if (cached) {
        return JSON.parse(cached);
      }

      // Get latest moisture reading
      const moisture = await sensorRepository.getLatestMoistureReading(fieldId);
      
      if (moisture) {
        // Cache the reading
        await this.redis.setex(
          cacheKey,
          this.CACHE_TTL,
          JSON.stringify(moisture)
        );

        // Update sensor last reading
        await sensorRepository.updateSensorLastReading(
          moisture.sensorId,
          moisture.time
        );

        logger.info({
          fieldId,
          moisturePercent: moisture.moisturePercent,
          depth: moisture.depth
        }, 'Moisture reading retrieved');
      }

      return moisture;
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get current moisture level');
      throw error;
    }
  }

  /**
   * Check if field needs irrigation based on sensor data
   */
  async checkIrrigationNeed(fieldId: string): Promise<{
    needsIrrigation: boolean;
    reason: string;
    data: any;
  }> {
    try {
      const sensorConfig = await sensorRepository.getFieldSensorConfig(fieldId);
      
      // Check water level first
      const waterLevel = await this.getCurrentWaterLevel(fieldId);
      
      if (waterLevel) {
        // Get AWD thresholds from config
        const thresholds = await this.getAWDThresholds(fieldId);
        
        if (waterLevel.waterLevelCm <= -thresholds.dryingDepth) {
          return {
            needsIrrigation: true,
            reason: 'water_level_threshold',
            data: {
              currentLevel: waterLevel.waterLevelCm,
              threshold: -thresholds.dryingDepth,
              source: waterLevel.source
            }
          };
        }
      }

      // Check moisture if available
      if (sensorConfig.hasMoistureSensor) {
        const moisture = await this.getCurrentMoistureLevel(fieldId);
        
        if (moisture && moisture.moisturePercent < this.MOISTURE_THRESHOLD_DRY) {
          return {
            needsIrrigation: true,
            reason: 'moisture_threshold',
            data: {
              currentMoisture: moisture.moisturePercent,
              threshold: this.MOISTURE_THRESHOLD_DRY
            }
          };
        }
      }

      // Check drying days if no sensors available
      if (!sensorConfig.hasWaterLevelSensor && !sensorConfig.hasMoistureSensor) {
        const daysSinceDrying = await this.getDaysSinceDryingStart(fieldId);
        
        if (daysSinceDrying >= (sensorConfig.dryingDayCount || this.DEFAULT_DRYING_DAYS)) {
          return {
            needsIrrigation: true,
            reason: 'drying_days_exceeded',
            data: {
              daysSinceDrying,
              threshold: sensorConfig.dryingDayCount || this.DEFAULT_DRYING_DAYS
            }
          };
        }
      }

      return {
        needsIrrigation: false,
        reason: 'within_thresholds',
        data: {
          waterLevel: waterLevel?.waterLevelCm,
          moisture: sensorConfig.hasMoistureSensor ? 
            (await this.getCurrentMoistureLevel(fieldId))?.moisturePercent : null
        }
      };
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to check irrigation need');
      throw error;
    }
  }

  /**
   * Get AWD thresholds for a field
   */
  private async getAWDThresholds(_fieldId: string): Promise<{
    dryingDepth: number;
    safeAwdDepth: number;
    emergencyThreshold: number;
  }> {
    // This will be implemented with the AWD configuration service
    // For now, return defaults
    return {
      dryingDepth: parseInt(process.env.DEFAULT_DRYING_DEPTH || '15'),
      safeAwdDepth: parseInt(process.env.SAFE_AWD_DEPTH || '10'),
      emergencyThreshold: parseInt(process.env.EMERGENCY_THRESHOLD || '25')
    };
  }

  /**
   * Calculate days since drying cycle started
   */
  private async getDaysSinceDryingStart(fieldId: string): Promise<number> {
    try {
      // Get from Redis state
      const stateKey = RedisKeys.fieldState(fieldId);
      const state = await this.redis.hget(stateKey, 'dryingStartDate');
      
      if (state) {
        const startDate = new Date(state);
        const now = new Date();
        const diffTime = Math.abs(now.getTime() - startDate.getTime());
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        return diffDays;
      }

      return 0;
    } catch (error) {
      logger.error({ error, field: fieldId }, 'Failed to get days since drying start');
      return 0;
    }
  }

  /**
   * Get sensor health status for a field
   */
  async getFieldSensorHealth(fieldId: string): Promise<{
    overall: 'healthy' | 'degraded' | 'critical';
    sensors: SensorStatus[];
    issues: string[];
  }> {
    try {
      const sensorConfig = await sensorRepository.getFieldSensorConfig(fieldId);
      const allSensorIds = [
        ...sensorConfig.waterLevelSensorIds,
        ...sensorConfig.moistureSensorIds
      ];

      const sensorStatuses: SensorStatus[] = [];
      const issues: string[] = [];
      let unhealthyCount = 0;

      for (const sensorId of allSensorIds) {
        const status = await sensorRepository.getSensorStatus(sensorId);
        if (status) {
          sensorStatuses.push(status);

          // Check for issues
          if (!status.isActive) {
            issues.push(`Sensor ${sensorId} is inactive`);
            unhealthyCount++;
          } else if (status.reliability < 0.5) {
            issues.push(`Sensor ${sensorId} has low reliability (${status.reliability})`);
            unhealthyCount++;
          }

          if (status.batteryLevel && status.batteryLevel < 3.0) {
            issues.push(`Sensor ${sensorId} has low battery (${status.batteryLevel}V)`);
          }
        }
      }

      // Determine overall health
      let overall: 'healthy' | 'degraded' | 'critical';
      if (unhealthyCount === 0) {
        overall = 'healthy';
      } else if (unhealthyCount < allSensorIds.length / 2) {
        overall = 'degraded';
      } else {
        overall = 'critical';
      }

      return {
        overall,
        sensors: sensorStatuses,
        issues
      };
    } catch (error) {
      logger.error({ error, fieldId }, 'Failed to get field sensor health');
      throw error;
    }
  }

  /**
   * Process incoming sensor data from Kafka
   */
  async processSensorData(data: {
    sensorId: string;
    fieldId: string;
    type: 'water_level' | 'moisture';
    value: number;
    timestamp: string;
    metadata?: any;
  }): Promise<void> {
    try {
      const { sensorId, fieldId, type, value, timestamp } = data;

      // Update cache
      if (type === 'water_level') {
        const reading: WaterLevelReading = {
          time: new Date(timestamp),
          sensorId,
          fieldId,
          waterLevelCm: value,
          source: 'sensor',
          ...data.metadata
        };

        const cacheKey = RedisKeys.sensorReading(`water_${fieldId}`);
        await this.redis.setex(
          cacheKey,
          this.CACHE_TTL,
          JSON.stringify(reading)
        );
      } else if (type === 'moisture') {
        const reading: MoistureReading = {
          time: new Date(timestamp),
          sensorId,
          fieldId,
          moisturePercent: value,
          depth: data.metadata?.depth || 0,
          ...data.metadata
        };

        const cacheKey = RedisKeys.sensorReading(`moisture_${fieldId}`);
        await this.redis.setex(
          cacheKey,
          this.CACHE_TTL,
          JSON.stringify(reading)
        );
      }

      // Update sensor last reading
      await sensorRepository.updateSensorLastReading(sensorId, new Date(timestamp));

      // Check if irrigation is needed
      const irrigationCheck = await this.checkIrrigationNeed(fieldId);
      if (irrigationCheck.needsIrrigation) {
        // This will trigger the AWD control algorithm
        logger.info({
          fieldId,
          reason: irrigationCheck.reason,
          data: irrigationCheck.data
        }, 'Irrigation needed based on sensor data');
        
        // TODO: Emit event to trigger irrigation
      }

      logger.debug({
        sensorId,
        fieldId,
        type,
        value
      }, 'Sensor data processed');
    } catch (error) {
      logger.error({ error, data }, 'Failed to process sensor data');
      throw error;
    }
  }
}

export const sensorManagementService = new SensorManagementService();